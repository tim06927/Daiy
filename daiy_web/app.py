"""Flask web app for grounded AI product recommendations.

Provides a user interface for bike component upgrade recommendations using
LLM-powered suggestions grounded in real product inventory.
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from config import (
    CSV_PATH,
    DEFAULT_BIKE_SPEED,
    DEFAULT_USE_CASE,
    FLASK_DEBUG,
    FLASK_HOST,
    FLASK_PORT,
    LLM_MODEL,
    MAX_CASSETTES,
    MAX_CHAINS,
)
from flask import Flask, Response, jsonify, render_template, request
from openai import OpenAI

client = OpenAI()
app = Flask(__name__)


# ---------- DATA MODEL & CATALOG LOADING ----------


@dataclass
class Product:
    category: str
    name: str
    url: str
    brand: Optional[str]
    price_text: Optional[str]
    application: Optional[str]
    speed: Optional[int]
    specs: Dict


def _parse_specs(s: str) -> Dict[str, Any]:
    """Parse JSON specs string, handling common CSV encoding issues.

    Args:
        s: JSON string, possibly with doubled quotes from CSV export.

    Returns:
        Parsed dict or empty dict if parsing fails.
    """
    if not isinstance(s, str) or not s.strip():
        return {}
    try:
        result = json.loads(s)
        return dict(result) if isinstance(result, dict) else {}
    except json.JSONDecodeError:
        # Handle doubled quotes from CSV export
        s2 = s.replace('""', '"')
        try:
            result = json.loads(s2)
            return dict(result) if isinstance(result, dict) else {}
        except json.JSONDecodeError:
            return {}


def load_catalog(path: str = CSV_PATH) -> pd.DataFrame:
    """Load and parse product catalog from CSV.

    Derives speed and application fields from raw data.

    Args:
        path: Path to product CSV file.

    Returns:
        DataFrame with parsed specs, derived speed, and application.
    """
    df = pd.read_csv(path)

    # Parse specs JSON
    if "specs" in df.columns:
        df["specs_dict"] = df["specs"].apply(_parse_specs)
    else:
        df["specs_dict"] = [{} for _ in range(len(df))]

    # Derive speed from chain gearing or specs
    def derive_speed(row: pd.Series) -> Optional[int]:
        cg = row.get("chain_gearing")
        if isinstance(cg, str):
            m = re.search(r"\d+", cg)
            if m:
                return int(m.group())

        specs = row["specs_dict"]
        g = specs.get("Gearing")
        if isinstance(g, str):
            m = re.search(r"\d+", g)
            if m:
                return int(m.group())
        return None

    df["speed"] = df.apply(derive_speed, axis=1)

    # Derive application from chain application or specs
    def derive_application(row: pd.Series) -> Optional[str]:
        ca = row.get("chain_application")
        if isinstance(ca, str):
            return ca
        specs = row["specs_dict"]
        app = specs.get("Application")
        return app if isinstance(app, str) else None

    df["application"] = df.apply(derive_application, axis=1)

    return df


# load once at startup
CATALOG_DF = load_catalog()


# ---------- CANDIDATE SELECTION & CONTEXT BUILDING ----------


def select_candidates(
    df: pd.DataFrame, bike_speed: int, use_case_substring: str
) -> Dict[str, List[Dict[str, Any]]]:
    """Filter products by speed and use case to create a candidate pool.

    Selects cassettes and chains from the inventory that match the bike's speed
    and intended use case. This narrowing is essential for grounding - it ensures
    the LLM can only recommend real products actually in stock.

    Args:
        df: Product catalog DataFrame with columns: speed, category, application, etc.
        bike_speed: Number of gears (e.g., 11 for 11-speed drivetrain).
        use_case_substring: Text to match in application field (e.g., "Road", "gravel").

    Returns:
        Dict with 'cassettes' and 'chains' keys, each containing a list of products.
        Each product is a dict with: name, url, brand, price, application, speed, specs.
    """
    cassettes = df[
        (df["category"] == "cassettes")
        & (df["speed"] == bike_speed)
        & df["application"].fillna("").str.contains(use_case_substring, case=False)
    ].head(MAX_CASSETTES)

    chains = df[(df["category"] == "chains") & (df["speed"] == bike_speed)].head(MAX_CHAINS)

    def df_to_list(subdf: pd.DataFrame) -> List[Dict[str, Any]]:
        out: List[Dict] = []
        for _, row in subdf.iterrows():
            out.append(
                {
                    "name": row["name"],
                    "url": row["url"],
                    "brand": row.get("brand"),
                    "price": row.get("price_text"),
                    "application": row.get("application"),
                    "speed": row.get("speed"),
                    "specs": row.get("specs_dict", {}),
                }
            )
        return out

    return {
        "cassettes": df_to_list(cassettes),
        "chains": df_to_list(chains),
    }


def build_grounding_context(problem_text: str) -> Dict[str, Any]:
    """Build the grounding context for LLM recommendation generation.

    Creates a structured JSON context that includes the user's project description,
    the current bike state, and a filtered pool of real products the LLM can recommend.
    Currently hard-coded for 11-speed road/gravel upgrades (future: make dynamic).

    The context structure guides the LLM to:
    1. Understand the user's specific constraints and goals
    2. Select only from real, available products (prevents hallucination)
    3. Provide product URLs and detailed reasoning

    Args:
        problem_text: User's description of their bike and upgrade goals.

    Returns:
        Dict with keys: 'project' (string), 'user_bike' (dict with constraints),
        'candidates' (dict with 'cassettes' and 'chains' lists).
    """
    bike_state = {
        "drivetrain_speed": DEFAULT_BIKE_SPEED,
        "current_cassette": "11-32 road cassette (example)",
        "use_case": "Road / light gravel",
        "user_problem_text": problem_text,
        "constraints": [
            "stay 11-speed",
            "wider range for climbing",
        ],
    }

    candidates = select_candidates(
        CATALOG_DF, bike_speed=DEFAULT_BIKE_SPEED, use_case_substring=DEFAULT_USE_CASE
    )

    return {
        "project": "Upgrade to wider 11-speed road cassette",
        "user_bike": bike_state,
        "candidates": candidates,
    }


# ---------- LLM CALL ----------


def make_prompt(context: dict) -> str:
    """Format the grounding context into a prompt for the LLM.

    Constructs a detailed prompt that instructs the LLM to:
    1. Act as an experienced bike mechanic
    2. Consider the user's specific goals and constraints
    3. Choose ONE cassette and ONE chain from the provided candidates
    4. Provide detailed reasoning (3-5 bullet points)
    5. Output a machine-readable JSON summary with product URLs

    The prompt explicitly forbids inventing products or using sources outside
    the provided candidate list.

    Args:
        context: Dict from build_grounding_context() with user_bike, candidates, etc.

    Returns:
        Formatted prompt string ready for LLM API submission.
    """
    return f"""
You are an experienced bike mechanic.

A user described their situation / project as:

\"\"\"{context["user_bike"]["user_problem_text"]}\"\"\"


They want to upgrade their cassette.

Here is the project and the available products from ONE shop.
You MUST ONLY recommend products from the lists below.
Do NOT invent other products or URLs.

CONTEXT (JSON):
{json.dumps(context, indent=2)}

TASK:
1. Choose ONE cassette and ONE matching chain from the candidates.
2. Explain in 3–5 short bullet points why they fit the user's bike and project.
   - cover speed compatibility
   - cover use case (road / gravel / MTB)
   - cover gear range (why this is better for climbing).
3. At the very end, output a short machine-readable summary in JSON with this shape:

{{
  "cassette_url": "...",
  "chain_url": "...",
  "notes": ["...", "..."]
}}

Answer in English.
""".strip()


def call_llm(prompt: str) -> str:
    """Call the OpenAI gpt-5-nano model with extended thinking (Responses API).

    Submits a prompt to the LLM and extracts the text response, handling the
    Responses API's special output format which includes reasoning blocks.
    The model may return multiple output items - we filter for the first one
    with actual content (skipping reasoning-only items).

    Args:
        prompt: The prompt string to send to the LLM.

    Returns:
        The text response from the LLM (excluding reasoning blocks).

    Raises:
        ValueError: If the response contains no actual content.
    """
    resp = client.responses.create(
        model=LLM_MODEL,
        input=prompt,
    )
    # Handle responses with reasoning blocks from gpt-5-nano
    for item in resp.output:
        if hasattr(item, "content") and item.content is not None:
            return item.content[0].text  # type: ignore[union-attr]
    raise ValueError("No content found in response")


def extract_json_summary(answer_text: str) -> Optional[Dict[str, Any]]:
    """Extract the JSON summary from the end of the LLM response.

    Looks for a JSON object containing cassette_url and chain_url fields.

    Args:
        answer_text: Full LLM response text.

    Returns:
        Parsed JSON dict if found, None otherwise.
    """
    match = re.search(r'\{[^{}]*"cassette_url"[^{}]*"chain_url"[^{}]*\}', answer_text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            return dict(result) if isinstance(result, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def remove_json_summary(answer_text: str) -> str:
    """Remove the machine-readable JSON summary from the answer text.

    Strips the JSON object from the end of the response.

    Args:
        answer_text: Full LLM response text.

    Returns:
        Answer text without the JSON summary.
    """
    return re.sub(
        r'\n*\{[^{}]*"cassette_url"[^{}]*"chain_url"[^{}]*\}$', "", answer_text, flags=re.DOTALL
    ).strip()


# ---------- FLASK ROUTES ----------


@app.route("/", methods=["GET"])
def index() -> str:
    """Render the main recommendation page."""
    return render_template("index.html")


@app.route("/api/recommend", methods=["POST"])
def api_recommend() -> Union[tuple[Response, int], Response]:
    """Generate AI recommendation for bike component upgrade.

    Request JSON: {"problem_text": "..."}

    Returns:
        JSON response with recommendation text, product candidates, and summary.
    """
    data = request.get_json(force=True)
    problem_text = data.get("problem_text", "").strip()

    if not problem_text:
        return jsonify({"error": "problem_text is required"}), 400

    context = build_grounding_context(problem_text)
    prompt = make_prompt(context)
    answer_text = call_llm(prompt)

    # Extract JSON summary and remove it from displayed text
    json_summary = extract_json_summary(answer_text)
    answer_text_clean = remove_json_summary(answer_text)

    # Build product list for display
    products = []

    for cass in context["candidates"]["cassettes"]:
        products.append(
            {
                "type": "cassette",
                "name": cass["name"],
                "brand": cass["brand"],
                "price": cass["price"],
                "url": cass["url"],
            }
        )
    for chain in context["candidates"]["chains"]:
        products.append(
            {
                "type": "chain",
                "name": chain["name"],
                "brand": chain["brand"],
                "price": chain["price"],
                "url": chain["url"],
            }
        )

    return jsonify(
        {
            "answer": answer_text_clean,
            "products": products,
            "summary": json_summary,  # Include for frontend if needed, but not displayed in main answer
        }
    )


if __name__ == "__main__":
    # For local demo use debug=True if you like
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
