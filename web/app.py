"""Flask web app for grounded AI product recommendations.

Provides a user interface for bike component upgrade recommendations using
LLM-powered suggestions grounded in real product inventory.
"""

import base64
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request
from openai import OpenAI

# Load environment variables from .env file (explicitly specify path)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from config import (  # noqa: E402
    CSV_PATH,
    FLASK_DEBUG,
    FLASK_HOST,
    FLASK_PORT,
    LLM_MODEL,
    MAX_CASSETTES,
    MAX_CHAINS,
    MAX_TOOLS,
)

# Initialize OpenAI client with API key from environment
api_key = os.getenv("OPENAI_API_KEY")
if not api_key or api_key == "your-api-key-here":
    raise ValueError("OPENAI_API_KEY not set in .env file or still has placeholder value")
client = OpenAI(api_key=api_key)
app = Flask(__name__)

# Setup LLM interaction logging
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"llm_interactions_{datetime.now().strftime('%Y%m%d')}.jsonl"


def log_interaction(event_type: str, data: Dict[str, Any]) -> None:
    """Log LLM interactions to a structured JSONL file.

    Args:
        event_type: Type of event (user_input, regex_inference, llm_call, llm_response, etc.)
        data: Event-specific data to log
    """
    log_entry = {"timestamp": datetime.now().isoformat(), "event_type": event_type, **data}
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


# ---------- BASIC AUTH ----------


def _basic_auth_creds() -> tuple[Optional[str], Optional[str]]:
    """Get demo credentials from environment."""
    return os.getenv("DEMO_USER"), os.getenv("DEMO_PASS")


def _unauthorized() -> Response:
    return Response(
        "Authentication required",
        401,
        {"WWW-Authenticate": 'Basic realm="Login Required"'},
    )


@app.before_request
def require_basic_auth() -> Optional[Response]:
    """
    Enforce HTTP Basic Auth for all routes.
    Skips enforcement if credentials are not configured (DEMO_USER/DEMO_PASS unset).
    """
    user, password = _basic_auth_creds()
    if not user or not password:
        return None  # auth disabled

    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return _unauthorized()

    try:
        decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
        username, passwd = decoded.split(":", 1)
    except Exception:
        return _unauthorized()

    if username == user and passwd == password:
        return None
    return _unauthorized()


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

    # Derive speed from chain gearing, specs, or product name
    def derive_speed(row: pd.Series) -> Optional[int]:
        # Try chain_gearing field first
        cg = row.get("chain_gearing")
        if isinstance(cg, str):
            m = re.search(r"\d+", cg)
            if m:
                return int(m.group())

        # Try specs Gearing
        specs = row["specs_dict"]
        g = specs.get("Gearing")
        if isinstance(g, str):
            m = re.search(r"\d+", g)
            if m:
                return int(m.group())

        # Fallback: extract speed from product name (e.g., "11-Speed", "12s")
        name = row.get("name", "")
        if isinstance(name, str):
            # Match patterns like "11-Speed", "11 Speed", "11s", "11-speed"
            m = re.search(r"(\d{1,2})[\-\s]?(?:speed|s(?:pd)?)\b", name, re.IGNORECASE)
            if m:
                return int(m.group(1))

        return None

    df["speed"] = df.apply(derive_speed, axis=1)

    # Derive application from chain application, specs, or product name
    def derive_application(row: pd.Series) -> Optional[str]:
        ca = row.get("chain_application")
        if isinstance(ca, str):
            return ca
        specs = row["specs_dict"]
        app = specs.get("Application")
        if isinstance(app, str):
            return app

        # Fallback: extract application keywords from product name
        name = row.get("name", "")
        if isinstance(name, str):
            name_lower = name.lower()
            # Check for common application keywords
            for keyword in ["road", "gravel", "mtb", "mountain", "e-bike", "ebike", "touring", "cx", "cyclocross"]:
                if keyword in name_lower:
                    return keyword.title()

        return None

    df["application"] = df.apply(derive_application, axis=1)

    return df


# ---------- CATALOG INITIALIZATION ----------

# load once at startup
CATALOG_DF = load_catalog()


# ---------- CANDIDATE SELECTION & CONTEXT BUILDING ----------


def select_candidates(
    df: pd.DataFrame, bike_speed: int, use_case_substring: str
) -> Dict[str, List[Dict[str, Any]]]:
    """Filter products by speed and use case to create a candidate pool.

    Selects cassettes, chains, and drivetrain tools from the inventory that match
    the bike's speed and intended use case. This narrowing is essential for grounding
    - it ensures the LLM can only recommend real products actually in stock.

    Args:
        df: Product catalog DataFrame with columns: speed, category, application, etc.
        bike_speed: Number of gears (e.g., 11 for 11-speed drivetrain).
        use_case_substring: Text to match in application field (e.g., "Road", "gravel").

    Returns:
        Dict with 'cassettes', 'chains', and 'drivetrain_tools' keys, each containing
        a list of products. Each product is a dict with: name, url, brand, price,
        application, speed, specs.
    """
    # Cassettes: try to filter by speed AND application, fall back to speed only
    cassettes = df[
        (df["category"] == "cassettes")
        & (df["speed"] == bike_speed)
        & df["application"].fillna("").str.contains(use_case_substring, case=False)
    ]
    if cassettes.empty:
        # Fall back to just speed filter if no application matches
        cassettes = df[
            (df["category"] == "cassettes") & (df["speed"] == bike_speed)
        ]
    cassettes = cassettes.head(MAX_CASSETTES)

    # Chains: filter by speed only
    chains = df[(df["category"] == "chains") & (df["speed"] == bike_speed)].head(MAX_CHAINS)

    tools = df[df["category"] == "drivetrain_tools"]
    if use_case_substring:
        filtered_tools = tools[
            tools["application"].fillna("").str.contains(use_case_substring, case=False)
        ]
        if not filtered_tools.empty:
            tools = filtered_tools
    tools = tools.head(MAX_TOOLS)

    def _clean(value: Any) -> Any:
        try:
            return None if pd.isna(value) else value
        except TypeError:
            return value

    def df_to_list(subdf: pd.DataFrame) -> List[Dict[str, Any]]:
        out: List[Dict] = []
        for _, row in subdf.iterrows():
            out.append(
                {
                    "name": _clean(row["name"]),
                    "url": _clean(row["url"]),
                    "brand": _clean(row.get("brand")),
                    "price": _clean(row.get("price_text")),
                    "application": _clean(row.get("application")),
                    "speed": _clean(row.get("speed")),
                    "specs": row.get("specs_dict", {}),
                }
            )
        return out

    return {
        "cassettes": df_to_list(cassettes),
        "chains": df_to_list(chains),
        "drivetrain_tools": df_to_list(tools),
    }


def _infer_bike_attributes(problem_text: str) -> Tuple[Optional[int], Optional[str]]:
    """Infer drivetrain speed and use case from user input.

    - Speed: looks for patterns like "11-speed", "12s", "10 spd".
    - Use case: keyword matching (road, gravel, mtb, commute, touring, e-bike).
    - Fallback: if contains any gearing keywords, assume 11-speed (most common for road).

    Returns:
        (speed, use_case) where speed is an int if detected, else None;
        use_case is a lowercase keyword if detected, else None.
    """
    text = problem_text.lower()

    speed: Optional[int] = None
    # Patterns: 12-speed, 12 spd, 12s
    m = re.search(r"(\d{1,2})\s*(?:-?\s*(?:speed|spd|s))\b", text)
    if m:
        try:
            speed = int(m.group(1))
        except ValueError:
            speed = None
    # No fallback guessing - require explicit mention

    use_case: Optional[str] = None
    keyword_map = {
        "gravel": "gravel",
        "mtb": "mtb",
        "mountain": "mtb",
        "trail": "mtb",
        "enduro": "mtb",
        "xc": "mtb",
        "downhill": "mtb",
        "dh": "mtb",
        "road": "road",
        "commute": "commute",
        "commuter": "commute",
        "urban": "commute",
        "city": "commute",
        "touring": "touring",
        "bikepacking": "touring",
        "e-bike": "e-bike",
        "ebike": "e-bike",
    }
    for key, value in keyword_map.items():
        if key in text:
            use_case = value
            break
    # No fallback guessing - require explicit mention

    return speed, use_case


# ---------- BIKE ATTRIBUTE INFERENCE & PARSING ----------


def _parse_selected_speed(value: Any) -> Optional[int]:
    """Parse user-provided speed (int or string like '11-speed')."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        m = re.search(r"(\d{1,2})", value)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                return None
    return None


def _request_clarification_options(
    problem_text: str,
    missing: List[str],
    image_base64: Optional[str] = None,
    image_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Ask the LLM to infer missing values from user text OR propose option lists.

    The LLM first tries to infer the missing information from the user's text.
    If it can infer values, it returns them directly with empty option lists.
    If it cannot infer, it returns option lists for the user to choose from.

    Optionally provides a user-uploaded photo (base64, truncated) so the LLM can
    leverage visual cues for drivetrain speed or use case. Photo metadata is carried
    through logging so we can audit when an image was uploaded and shared.

    Returns:
        Dict with keys:
        - "inferred_speed": int or None (if LLM could infer from text)
        - "inferred_use_case": str or None (if LLM could infer from text)
        - "speed_options": list (if LLM needs to ask user)
        - "use_case_options": list (if LLM needs to ask user)
    """
    base_len = len(image_base64.strip()) if isinstance(image_base64, str) else 0
    image_meta_for_log = {
        **(image_meta or {}),
        "shared_with_llm": bool(base_len),
        "shared_chars": base_len,
        "truncated_in_prompt": False,
    }

    prompt = (
        "You are assisting a bike components recommender. The user wrote:\n"
        f'"""{problem_text}"""\n\n'
        f"The regex-based system could not automatically detect: {', '.join(missing)}.\n\n"
        "YOUR TASK: Carefully analyze the user's text and either:\n"
        "1. INFER the missing values if they are clearly stated or strongly implied, OR\n"
        "2. PROPOSE option lists if the information is truly ambiguous or absent.\n\n"
        "Respond with pure JSON ONLY (no prose), using this exact structure:\n"
        "{\n"
        '  "inferred_speed": 11,  // int if you can infer, null if you cannot\n'
        '  "inferred_use_case": "road",  // lowercase string if you can infer, null if you cannot\n'
        '  "speed_options": [],  // empty if inferred, else ["8-speed", "11-speed", "12-speed"]\n'
        '  "use_case_options": []  // empty if inferred, else ["road", "gravel", "mtb"]\n'
        "}\n\n"
        "RULES:\n"
        "- If you can determine the speed/use_case from context, set inferred_* and leave options empty\n"
        "- Only populate options lists if you genuinely cannot infer the value\n"
        "- For speed: look for mentions like '12-speed', 'shimano 105' (11-speed), 'ultegra' (11/12), etc.\n"
        "- For use_case: look for bike types, terrain, riding style, component mentions\n"
        "- Keep option lists to max 5 items with short labels\n"
        "- Use lowercase for use_case values: 'road', 'gravel', 'mtb', 'commute', 'touring', etc.\n"
    )

    log_interaction(
        "llm_call_clarification",
        {
            "model": LLM_MODEL,
            "prompt": prompt,
            "missing_keys": missing,
            "user_text": problem_text,
            "image_attached": bool(base_len),
            "image_meta": image_meta_for_log,
        },
    )

    input_payload = [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}]
    if base_len:
        input_payload.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{str(image_base64)}",
                    }
                ],
            }
        )

    resp = client.responses.create(
        model=LLM_MODEL,
        input=input_payload,
    )
    for item in resp.output:
        if hasattr(item, "content") and item.content is not None:
            raw = item.content[0].text  # type: ignore[union-attr]

            log_interaction(
                "llm_response_clarification",
                {
                    "model": LLM_MODEL,
                    "raw_response": raw,
                },
            )

            try:
                parsed = json.loads(raw)
                result = {
                    "inferred_speed": parsed.get("inferred_speed"),
                    "inferred_use_case": parsed.get("inferred_use_case"),
                    "speed_options": (
                        parsed.get("speed_options", [])
                        if isinstance(parsed.get("speed_options"), list)
                        else []
                    ),
                    "use_case_options": (
                        parsed.get("use_case_options", [])
                        if isinstance(parsed.get("use_case_options"), list)
                        else []
                    ),
                }
                log_interaction("llm_inference_result", result)
                return result
            except json.JSONDecodeError as e:
                log_interaction("llm_parse_error", {"error": str(e), "raw": raw})
                # Fallback to asking with default options
                return {
                    "inferred_speed": None,
                    "inferred_use_case": None,
                    "speed_options": (
                        ["8-speed", "9-speed", "10-speed", "11-speed", "12-speed"]
                        if "drivetrain_speed" in missing
                        else []
                    ),
                    "use_case_options": (
                        ["road", "gravel", "mtb", "commute", "touring"]
                        if "use_case" in missing
                        else []
                    ),
                }
    return {
        "inferred_speed": None,
        "inferred_use_case": None,
        "speed_options": (
            ["8-speed", "9-speed", "10-speed", "11-speed", "12-speed"]
            if "drivetrain_speed" in missing
            else []
        ),
        "use_case_options": (
            ["road", "gravel", "mtb", "commute", "touring"] if "use_case" in missing else []
        ),
    }


# ---------- CONTEXT & GROUNDING BUILDING ----------


def build_grounding_context(
    problem_text: str, bike_speed: int, use_case: str, image_base64: Optional[str] = None
) -> Dict[str, Any]:
    """Build the grounding context for LLM recommendation generation.

    Creates a structured JSON context that includes the user's project description,
    the current bike state, and a filtered pool of real products the LLM can recommend.
    Optionally includes a compressed photo provided by the user.

    The context structure guides the LLM to:
    1. Understand the user's specific constraints and goals
    2. Select only from real, available products (prevents hallucination)
    3. Provide product URLs and detailed reasoning

    Args:
        problem_text: User's description of their bike and upgrade goals.
        bike_speed: Detected drivetrain speed from user text.
        use_case: Detected use case keyword from user text.

    Returns:
        Dict with keys: 'project' (string), 'user_bike' (dict with constraints),
        'candidates' (dict with cassettes, chains, drivetrain_tools lists), and
        optional 'image_base64'.
    """
    bike_state = {
        "drivetrain_speed": bike_speed,
        "use_case": use_case,
        "user_problem_text": problem_text,
        "constraints": [
            f"stay {bike_speed}-speed",
            "match intended use case",
        ],
    }

    candidates = select_candidates(CATALOG_DF, bike_speed=bike_speed, use_case_substring=use_case)

    return {
        "project": "Drivetrain upgrade (cassette, chain, tools)",
        "user_bike": bike_state,
        "candidates": candidates,
        "image_base64": image_base64,
    }


# ---------- LLM CALL ----------


def make_prompt(context: dict, image_attached: bool = False) -> str:
    """Format the grounding context into a structured prompt for the LLM.

    Instructs the model to return *only* JSON with:
    - why_it_fits: bullets
    - suggested_workflow: ordered steps
    - checklist: tools/parts
    - product_ranking: best + alternative indices per category
    """

    def _fmt_products(label: str, products: List[Dict[str, Any]]) -> str:
        if not products:
            return f"{label}: []"
        lines = [f"{label} (0-based index, use only these):"]
        for idx, p in enumerate(products):
            lines.append(
                f"  {idx}: {p.get('name')} | brand: {p.get('brand')} | speed: {p.get('speed')} | application: {p.get('application')} | url: {p.get('url')}"
            )
        return "\n".join(lines)

    cassette_block = _fmt_products("Cassettes", context["candidates"].get("cassettes", []))
    chain_block = _fmt_products("Chains", context["candidates"].get("chains", []))
    tools_block = _fmt_products(
        "Drivetrain Tools", context["candidates"].get("drivetrain_tools", [])
    )
    user_text = context["user_bike"]["user_problem_text"]
    image_note = (
        "\nUser uploaded a bike photo (attached as image input). "
        "Consider visual cues (cassette sprocket count, derailleur style, tire/terrain hints) if relevant.\n"
        if image_attached
        else ""
    )

    return (
        "You are an experienced bike mechanic. Recommend ONE cassette, ONE chain, and at least ONE drivetrain tool from the provided candidates only.\n\n"
        f'User description:\n"""{user_text}"""\n\n'
        f"Detected drivetrain speed: {context['user_bike']['drivetrain_speed']}-speed.\n"
        f"Detected use case: {context['user_bike'].get('use_case', 'unspecified')}.\n"
        f"{image_note}\n"
        "Candidate products (do NOT invent anything else):\n"
        f"{cassette_block}\n"
        f"{chain_block}\n"
        f"{tools_block}\n\n"
        "RESPONSE FORMAT (return JSON ONLY, no prose):\n"
        "{\n"
        '  "diagnosis": "Short 1-sentence diagnosis of user problem",\n'
        '  "sections": {\n'
        '    "why_it_fits": ["bullet 1", "bullet 2", "bullet 3"],\n'
        '    "suggested_workflow": ["step 1", "step 2", "step 3"],\n'
        '    "checklist": ["tool 1", "part 1", "consumable 1"]\n'
        "  },\n"
        '  "product_ranking": {\n'
        '    "cassettes": {\n'
        '      "best_index": 0,\n'
        '      "alternatives": [1, 2],\n'
        '      "why_fits": {"0": "Fits explanation for product 0", "1": "Fits for product 1", "2": "Fits for product 2"}\n'
        '    },\n'
        '    "chains": {\n'
        '      "best_index": 0,\n'
        '      "alternatives": [1, 2],\n'
        '      "why_fits": {"0": "Fits explanation for product 0", "1": "Fits for product 1"}\n'
        '    },\n'
        '    "drivetrain_tools": {\n'
        '      "best_index": 0,\n'
        '      "alternatives": [1],\n'
        '      "why_fits": {"0": "Essential for cassette removal", "1": "Needed for chain installation"}\n'
        '    }\n'
        "  }\n"
        "}\n\n"
        "RULES:\n"
        "- Use 0-based indices that exist in the candidate lists above.\n"
        "- Choose exactly one best_index per category (cassettes, chains, drivetrain_tools); alternatives are optional and must be unique.\n"
        "- For EACH recommended product (best + alternatives), include a why_fits entry explaining why it matches the user's needs.\n"
        "- Keep why_fits explanations short (8-15 words), specific to the user's situation.\n"
        "- Keep bullets concise (max ~15 words each), 3-5 bullets for why_it_fits.\n"
        "- Provide 3-6 workflow steps, actionable and ordered.\n"
        "- Provide a checklist of 5-10 concise items (tools/parts/consumables).\n"
        "- Do not include any text outside the JSON."
    )


def call_llm(
    prompt: str, image_base64: Optional[str] = None, image_meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Call the LLM and parse the structured JSON response.

    Returns a dict with sections + product_ranking. Falls back to empty dict on failure.
    """
    log_interaction(
        "llm_call_recommendation",
        {
            "model": LLM_MODEL,
            "prompt": prompt,
            "image_meta": image_meta or {},
            "image_attached": bool(image_base64),
        },
    )

    input_payload = [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}]
    if isinstance(image_base64, str) and image_base64.strip():
        input_payload.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{image_base64.strip()}",
                    }
                ],
            }
        )

    resp = client.responses.create(
        model=LLM_MODEL,
        input=input_payload,
    )

    for item in resp.output:
        if hasattr(item, "content") and item.content is not None:
            raw = item.content[0].text  # type: ignore[union-attr]

            log_interaction(
                "llm_response_recommendation",
                {
                    "model": LLM_MODEL,
                    "raw_response": raw,
                },
            )

            try:
                parsed = json.loads(raw)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError as e:
                log_interaction("llm_parse_error_recommendation", {"error": str(e), "raw": raw})
                return {}

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
    selected_speed = _parse_selected_speed(data.get("selected_speed"))
    selected_use_case = data.get("selected_use_case")
    if isinstance(selected_use_case, str):
        selected_use_case = selected_use_case.strip().lower() or None
    else:
        selected_use_case = None

    raw_image_b64 = data.get("image_base64")
    image_base64 = raw_image_b64.strip() if isinstance(raw_image_b64, str) else None
    image_meta = {
        "uploaded": bool(image_base64),
        "received_chars": len(raw_image_b64) if isinstance(raw_image_b64, str) else 0,
        "stored_chars": len(image_base64) if isinstance(image_base64, str) else 0,
        "truncated_to_120k": False,
    }
    if image_base64 and len(image_base64) > 120_000:
        # safety: limit payload size, keep the head
        image_base64 = image_base64[:120_000]
        image_meta["stored_chars"] = len(image_base64)
        image_meta["truncated_to_120k"] = True

    if not problem_text:
        return jsonify({"error": "problem_text is required"}), 400

    # Only log "user_input" event if this is a NEW problem (no selections made yet)
    # This way, selections during clarification don't start a new session
    if selected_speed is None and selected_use_case is None:
        log_interaction(
            "user_input",
            {
                "problem_text": problem_text,
                "image_meta": image_meta,
            },
        )
    else:
        # Log user selections separately (not as a new session)
        log_interaction(
            "user_selection",
            {
                "problem_text": problem_text,
                "selected_speed": selected_speed,
                "selected_use_case": selected_use_case,
                "image_meta": image_meta,
            },
        )

    # Inference: only if user hasn't already selected via button
    inferred_speed, inferred_use_case = _infer_bike_attributes(problem_text)
    bike_speed = selected_speed or inferred_speed
    use_case = selected_use_case or inferred_use_case

    log_interaction(
        "regex_inference",
        {
            "inferred_speed": inferred_speed,
            "inferred_use_case": inferred_use_case,
            "final_speed": bike_speed,
            "final_use_case": use_case,
        },
    )

    # Debug logging
    print(f"[DEBUG] Inference: speed={inferred_speed}, use_case={inferred_use_case}")
    print(f"[DEBUG] Selected: speed={selected_speed}, use_case={selected_use_case}")
    print(f"[DEBUG] Final: speed={bike_speed}, use_case={use_case}")

    missing_keys: List[str] = []
    if bike_speed is None:
        missing_keys.append("drivetrain_speed")
    if use_case is None:
        missing_keys.append("use_case")

    # If something is missing after regex, try LLM inference
    # BUT only if this is the first request (no user selections yet)
    if missing_keys and selected_speed is None and selected_use_case is None:
        # First time - try LLM inference before asking user
        llm_result = _request_clarification_options(
            problem_text, missing_keys, image_base64=image_base64, image_meta=image_meta
        )

        # Use LLM's inferred values if available
        if llm_result.get("inferred_speed") is not None and "drivetrain_speed" in missing_keys:
            bike_speed = llm_result["inferred_speed"]
            missing_keys.remove("drivetrain_speed")
            print(f"[DEBUG] LLM inferred speed: {bike_speed}")

        if llm_result.get("inferred_use_case") is not None and "use_case" in missing_keys:
            use_case = llm_result["inferred_use_case"]
            missing_keys.remove("use_case")
            print(f"[DEBUG] LLM inferred use_case: {use_case}")

        # If there are STILL missing values after LLM inference, ask user to select from options
        if missing_keys:
            options = {
                "speed_options": llm_result.get("speed_options", []),
                "use_case_options": llm_result.get("use_case_options", []),
            }
            hints = {
                "drivetrain_speed": "Count the cogs on your rear cassette, or check the number printed on your shifter (e.g., '11' for 11-speed).",
                "use_case": "Think about where you ride most: smooth roads, gravel paths, mountain trails, or city commutes.",
            }
            payload = {
                "need_clarification": True,
                "missing": missing_keys,
                "options": options,
                "hints": hints,
            }
            # Persist any inferred values so the frontend can keep them between requests
            if bike_speed is not None:
                payload["inferred_speed"] = bike_speed
            if use_case is not None:
                payload["inferred_use_case"] = use_case

            return jsonify(payload), 200
    elif missing_keys:
        # User already made a selection but something is still missing
        # This shouldn't happen, but handle it gracefully with defaults
        print(f"[WARNING] Still missing {missing_keys} after user selection")
        if bike_speed is None:
            bike_speed = 11  # Default fallback
        if use_case is None:
            use_case = "road"  # Default fallback

    assert bike_speed is not None and use_case is not None

    context = build_grounding_context(
        problem_text, bike_speed=bike_speed, use_case=use_case, image_base64=image_base64
    )
    prompt = make_prompt(context, image_attached=bool(image_base64))

    def _default_sections() -> Dict[str, List[str]]:
        return {
            "why_it_fits": [
                f"Matches {bike_speed}-speed drivetrain without extra parts",
                f"Optimized for {use_case} riding",
                "Gearing chosen for better climbing while keeping flats comfortable",
            ],
            "suggested_workflow": [
                "Confirm freehub body and drivetrain speed",
                "Install cassette with proper torque and fresh grease",
                "Size and install new chain, check shifting",
                "Test ride and fine-tune indexing",
            ],
            "checklist": [
                "Cassette lockring tool + torque wrench",
                "Chain breaker or quick-link pliers",
                "Grease + rags",
                "Floor pump and stand",
                "Gloves and eye protection",
            ],
        }

    def _coerce_str_list(value: Any, fallback: List[str]) -> List[str]:
        if isinstance(value, list):
            out = [str(v).strip() for v in value if str(v).strip()]
            return out if out else fallback
        return fallback

    def _simplify_product(prod: Dict[str, Any], prod_type: str) -> Dict[str, Any]:
        def _clean(value: Any) -> Any:
            try:
                return None if pd.isna(value) else value
            except TypeError:
                return value

        return {
            "type": prod_type,
            "name": _clean(prod.get("name")),
            "brand": _clean(prod.get("brand")),
            "price": _clean(prod.get("price")),
            "url": _clean(prod.get("url")),
            "application": _clean(prod.get("application")),
            "speed": _clean(prod.get("speed")),
        }

    # Prepare photo metadata for downstream logging
    base_len = len(image_base64) if isinstance(image_base64, str) else 0
    image_meta_for_llm = {
        **image_meta,
        "shared_with_llm": bool(base_len),
        "shared_chars": base_len,
        "truncated_in_prompt": False,
    }

    # Call LLM and parse structured content
    try:
        llm_payload = call_llm(prompt, image_base64=image_base64, image_meta=image_meta_for_llm)
    except ValueError:
        llm_payload = {}

    sections_raw = llm_payload.get("sections", {}) if isinstance(llm_payload, dict) else {}
    ranking_raw = llm_payload.get("product_ranking", {}) if isinstance(llm_payload, dict) else {}
    diagnosis = llm_payload.get("diagnosis", "") if isinstance(llm_payload, dict) else ""

    sections = _default_sections()
    sections["why_it_fits"] = _coerce_str_list(
        sections_raw.get("why_it_fits"), sections["why_it_fits"]
    )
    sections["suggested_workflow"] = _coerce_str_list(
        sections_raw.get("suggested_workflow"), sections["suggested_workflow"]
    )
    sections["checklist"] = _coerce_str_list(sections_raw.get("checklist"), sections["checklist"])

    # Build products with best + alternatives per category
    products_by_category: List[Dict[str, Any]] = []

    def _build_row(key: str, label: str) -> None:
        candidates = context["candidates"].get(key, [])
        if not candidates:
            return

        rank_info = ranking_raw.get(key, {}) if isinstance(ranking_raw, dict) else {}
        best_idx = rank_info.get("best_index", 0)
        if not isinstance(best_idx, int) or best_idx < 0 or best_idx >= len(candidates):
            best_idx = 0

        alt_indices_raw = rank_info.get("alternatives", []) if isinstance(rank_info, dict) else []
        alt_indices: List[int] = []
        if isinstance(alt_indices_raw, list):
            for item in alt_indices_raw:
                if isinstance(item, int) and 0 <= item < len(candidates) and item != best_idx:
                    alt_indices.append(item)

        # Fill remaining alternatives to show as many as possible
        remaining = [i for i in range(len(candidates)) if i not in alt_indices and i != best_idx]
        alt_indices = alt_indices + remaining

        prod_type_map = {
            "cassettes": "cassette",
            "chains": "chain",
            "drivetrain_tools": "tool",
        }
        prod_type = prod_type_map.get(key, "product")

        # Get why_fits explanations from LLM response
        why_fits = rank_info.get("why_fits", {}) if isinstance(rank_info, dict) else {}
        if not isinstance(why_fits, dict):
            why_fits = {}

        def _add_why_fits(prod: Dict[str, Any], idx: int) -> Dict[str, Any]:
            """Add why_it_fits field to product based on LLM response."""
            prod_with_why = _simplify_product(prod, prod_type=prod_type)
            # Try both string and int keys for robustness
            why_text = why_fits.get(str(idx)) or why_fits.get(idx) or ""
            prod_with_why["why_it_fits"] = why_text if isinstance(why_text, str) else ""
            return prod_with_why

        best_prod = _add_why_fits(candidates[best_idx], best_idx)
        alt_prods = [_add_why_fits(candidates[i], i) for i in alt_indices]

        products_by_category.append(
            {
                "category": label,
                "category_key": key,
                "best": best_prod,
                "alternatives": alt_prods,
            }
        )

    _build_row("cassettes", "Cassettes")
    _build_row("chains", "Chains")
    _build_row("drivetrain_tools", "Drivetrain tools")

    if not products_by_category:
        return (
            jsonify(
                {
                    "error": "No matching products found for the inferred bike speed/use case.",
                    "inferred": {
                        "drivetrain_speed": bike_speed,
                        "use_case": use_case,
                    },
                    "hint": "Try specifying your speed (e.g., '12-speed') and use case (road, gravel, mtb).",
                }
            ),
            404,
        )

    return jsonify(
        {
            "diagnosis": diagnosis,
            "sections": sections,
            "products_by_category": products_by_category,
            "inferred_speed": bike_speed,
            "inferred_use_case": use_case,
        }
    )


if __name__ == "__main__":
    # For local demo use debug=True if you like
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
