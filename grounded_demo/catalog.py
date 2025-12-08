# catalog.py
import json
import re
from dataclasses import dataclass
from typing import Optional, Dict, List

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
    """
    Load the scraped bc_products_sample.csv and derive a few helpful columns:
    - specs_dict: parsed JSON from 'specs' column
    - speed: numeric speed (e.g. 9, 11) derived from chain_gearing / Gearing
    - application: from chain_application or specs.Application
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
    """
    Very first, dumb candidate selector:
    - cassettes: same speed & application contains use_case
    - chains: same speed
    Returns simple lists of dicts the LLM can consume.
    """
    # cassettes: same speed & application matches use_case
    cassettes = df[
        (df["category"] == "cassettes")
        & (df["speed"] == bike_speed)
        & df["application"].fillna("").str.contains(use_case, case=False)
    ].head(5)

    # chains: same speed (for now, ignore use_case)
    chains = df[
        (df["category"] == "chains")
        & (df["speed"] == bike_speed)
    ].head(5)

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
    """
    Build the JSON context we will hand to the LLM:
    - project description
    - user bike state
    - candidate products from the catalog
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
