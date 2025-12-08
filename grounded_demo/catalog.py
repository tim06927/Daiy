"""Product catalog loading and context building for grounded recommendations.

This module handles loading bike component data from CSV and preparing it as
structured context for the LLM. The grounding context ensures recommendations
are constrained to real, available products.
"""

import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

CSV_PATH = "../data/bc_products_sample.csv"


@dataclass
class Product:
    category: str
    name: str
    url: str
    brand: Optional[str]
    price_text: Optional[str]
    application: Optional[str]
    speed: Optional[int]
    raw_specs: Dict


def load_catalog(path: str = CSV_PATH) -> pd.DataFrame:
    """Load and enhance the product catalog with derived columns.

    Reads the CSV and adds computed fields:
    - specs_dict: Parses the JSON-formatted specs column
    - speed: Extracts numeric speed (e.g., 9, 11) from chain_gearing or specs
    - application: Derives use case (road, gravel, MTB, etc.) from chain_application
               or specs fields

    Args:
        path: Path to the CSV file (default: ../data/bc_products_sample.csv).

    Returns:
        DataFrame with original columns plus specs_dict, speed, and application.
    """
    df = pd.read_csv(path)

    # --- parse specs JSON safely ---
    def parse_specs(s):
        if not isinstance(s, str) or not s.strip():
            return {}
        # try plain JSON first
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            # common CSV case: inner quotes are doubled
            s2 = s.replace('""', '"')
            try:
                return json.loads(s2)
            except Exception:
                return {}

    if "specs" in df.columns:
        df["specs_dict"] = df["specs"].apply(parse_specs)
    else:
        df["specs_dict"] = [{} for _ in range(len(df))]

    # --- derive speed ---
    def derive_speed(row):
        # chains: use chain_gearing if present
        cg = row.get("chain_gearing")
        if isinstance(cg, str):
            m = re.search(r"\d+", cg)
            if m:
                return int(m.group())

        # fallback: look into specs.Gearing
        specs = row["specs_dict"]
        g = specs.get("Gearing")
        if isinstance(g, str):
            m = re.search(r"\d+", g)
            if m:
                return int(m.group())

        return None

    df["speed"] = df.apply(derive_speed, axis=1)

    # --- derive application ---
    def derive_application(row):
        ca = row.get("chain_application")
        if isinstance(ca, str):
            return ca
        specs = row["specs_dict"]
        app = specs.get("Application")
        if isinstance(app, str):
            return app
        return None

    df["application"] = df.apply(derive_application, axis=1)

    return df


def select_candidates(df: pd.DataFrame, bike_speed: int, use_case: str) -> Dict[str, List[Dict]]:
    """Filter products to create a candidate pool for LLM recommendation.

    Selects cassettes and chains that match the bike's speed and use case.
    This filtering is crucial for grounding - it restricts the LLM to real
    products we can actually recommend.

    Args:
        df: Product catalog DataFrame (from load_catalog()).
        bike_speed: Drivetrain speed in gears (e.g., 11 for 11-speed).
        use_case: Use case string to match (e.g., "Road", "gravel").

    Returns:
        Dict with 'cassettes' and 'chains' keys, each containing a list of
        product dicts with: name, url, brand, price, application, speed, specs.
    """
    # cassettes: same speed & application matches use_case
    cassettes = df[
        (df["category"] == "cassettes")
        & (df["speed"] == bike_speed)
        & df["application"].fillna("").str.contains(use_case, case=False)
    ].head(5)

    # chains: same speed (for now, ignore use_case)
    chains = df[(df["category"] == "chains") & (df["speed"] == bike_speed)].head(5)

    def df_to_simple_list(subdf: pd.DataFrame) -> List[Dict]:
        result: List[Dict] = []
        for _, row in subdf.iterrows():
            result.append(
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
        return result

    return {
        "cassettes": df_to_simple_list(cassettes),
        "chains": df_to_simple_list(chains),
        # later: add tools, gloves, etc.
    }


def build_grounding_context(df: pd.DataFrame) -> Dict:
    """Build the grounding context for LLM recommendation generation.

    Creates a structured JSON context with the user's bike state, project goals,
    and candidate products. This context prevents LLM hallucination by limiting
    recommendations to real inventory.

    Currently hard-coded for an 11-speed road/gravel upgrade scenario.
    In production, this would be parameterized by actual user input.

    Args:
        df: Product catalog DataFrame (from load_catalog()).

    Returns:
        Dict with keys: 'project' (string), 'user_bike' (bike state dict),
        and 'candidates' (cassettes and chains lists).
    """
    # example “user project”
    bike_state = {
        "drivetrain_speed": 11,
        "current_cassette": "11-32 road cassette",
        "use_case": "Road / light gravel",
        "constraints": [
            "stay 11-speed",
            "wider range for climbing",
        ],
    }

    candidates = select_candidates(df, bike_speed=11, use_case="Road")

    return {
        "project": "Upgrade to wider 11-speed road cassette",
        "user_bike": bike_state,
        "candidates": candidates,
    }


if __name__ == "__main__":
    # quick self-test / inspect
    df = load_catalog()
    ctx = build_grounding_context(df)
    print(json.dumps(ctx, indent=2))
