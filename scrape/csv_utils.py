"""Legacy CSV utilities - deprecated, use database directly."""

import csv
from typing import Dict, List, Optional, Tuple

__all__ = [
    "load_existing_products",
]


def load_existing_products(path: str) -> Tuple[List[Dict[str, str]], List[str]]:
    """Load existing products from CSV if present.

    Returns a tuple of (rows, fieldnames).
    
    DEPRECATED: Use database directly instead.
    """
    import os
    if not os.path.exists(path):
        return [], []

    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
    return rows, fieldnames
