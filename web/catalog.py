"""Catalog loading and management for the Daiy web app.

This module handles loading the product catalog from CSV and provides
a shared instance that can be used by multiple modules.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

# Handle imports for both direct execution and package import
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).parent))
    from config import CSV_PATH
else:
    from .config import CSV_PATH

__all__ = ["load_catalog", "get_catalog", "CATALOG_DF"]


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
    # Load with optimized dtypes for memory efficiency
    # Let pandas infer types instead of forcing everything to string
    # This can save 30-50% memory compared to dtype=str
    df = pd.read_csv(path, low_memory=False)

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


# Singleton catalog instance - loaded once at module import
CATALOG_DF: pd.DataFrame = load_catalog()


def get_catalog() -> pd.DataFrame:
    """Get the shared catalog DataFrame.
    
    Returns:
        The loaded product catalog.
    """
    return CATALOG_DF
