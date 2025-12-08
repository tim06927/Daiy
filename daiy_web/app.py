import os
import json
import re

from dataclasses import dataclass
from typing import Optional, Dict, List

import pandas as pd
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

from config import CSV_PATH, LLM_MODEL, FLASK_HOST, FLASK_PORT, FLASK_DEBUG
from config import DEFAULT_BIKE_SPEED, DEFAULT_USE_CASE, MAX_CASSETTES, MAX_CHAINS

# Set OPENAI_API_KEY in your environment before running
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


def _parse_specs(s: str) -> Dict:
    if not isinstance(s, str) or not s.strip():
        return {}
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # common CSV pattern: doubled quotes
        s2 = s.replace('""', '"')
        try:
            return json.loads(s2)
        except Exception:
            return {}


def load_catalog(path: str = CSV_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)

    # specs JSON
    if "specs" in df.columns:
        df["specs_dict"] = df["specs"].apply(_parse_specs)
    else:
        df["specs_dict"] = [{} for _ in range(len(df))]

    # derive speed
    def derive_speed(row):
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

    # derive application
    def derive_application(row):
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

def select_candidates(df: pd.DataFrame, bike_speed: int, use_case_substring: str) -> Dict[str, List[Dict]]:
    """
    Very simple selector:
    - cassettes: same speed & application contains use_case_substring
    - chains: same speed
    """
    cassettes = df[
        (df["category"] == "cassettes")
        & (df["speed"] == bike_speed)
        & df["application"].fillna("").str.contains(use_case_substring, case=False)
    ].head(MAX_CASSETTES)

    chains = df[
        (df["category"] == "chains")
        & (df["speed"] == bike_speed)
    ].head(MAX_CHAINS)

    def df_to_list(subdf: pd.DataFrame) -> List[Dict]:
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


def build_grounding_context(problem_text: str) -> Dict:
    """
    Builds the JSON context for the LLM.
    For now we hard-code an 11-speed road-ish upgrade scenario.
    The user's problem_text is included for flavour.
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

    candidates = select_candidates(CATALOG_DF, bike_speed=DEFAULT_BIKE_SPEED, use_case_substring=DEFAULT_USE_CASE)

    return {
        "project": "Upgrade to wider 11-speed road cassette",
        "user_bike": bike_state,
        "candidates": candidates,
    }


# ---------- LLM CALL ----------

def make_prompt(context: dict) -> str:
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
    resp = client.responses.create(
        model=LLM_MODEL,
        input=prompt,
    )
    # Handle responses with reasoning blocks
    for item in resp.output:
        if hasattr(item, "content") and item.content is not None:
            return item.content[0].text
    raise ValueError("No content found in response")


def extract_json_summary(answer_text: str) -> Optional[Dict]:
    """
    Extract the JSON summary from the end of the LLM response.
    Returns the JSON object if found, None otherwise.
    """
    # Look for JSON pattern at the end of the response
    import re
    match = re.search(r'\{[^{}]*"cassette_url"[^{}]*"chain_url"[^{}]*\}', answer_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None
    return None


def remove_json_summary(answer_text: str) -> str:
    """
    Remove the machine-readable JSON summary from the answer text.
    """
    # Remove the JSON object from the end
    import re
    return re.sub(r'\n*\{[^{}]*"cassette_url"[^{}]*"chain_url"[^{}]*\}$', '', answer_text, flags=re.DOTALL).strip()


# ---------- FLASK ROUTES ----------

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/api/recommend", methods=["POST"])
def api_recommend():
    """
    Expects JSON: { "problem_text": "..." }
    Ignores any image for now (dummy upload).
    Returns: { "answer": "...", "products": [ {name, url, brand, price}, ... ] }
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
