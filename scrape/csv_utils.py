"""CSV export and import utilities."""

import csv
import json
import os
from dataclasses import asdict
from typing import Dict, Iterable, List, Optional, Tuple

from scrape.models import Product


def load_existing_products(path: str) -> Tuple[List[Dict[str, str]], List[str]]:
    """Load existing products from CSV if present.

    Returns a tuple of (rows, fieldnames).
    """
    if not os.path.exists(path):
        return [], []

    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []
    return rows, fieldnames


def product_to_row(product: Product) -> Dict[str, str]:
    """Convert Product dataclass into a CSV-ready row."""
    row = asdict(product)
    if row.get("specs") is not None:
        row["specs"] = json.dumps(row["specs"], ensure_ascii=False)
    return row


def save_products_to_csv(
    products: Iterable[Product],
    path: str,
    existing_rows: Optional[List[Dict[str, str]]] = None,
    fieldnames: Optional[List[str]] = None,
) -> None:
    """Save products to CSV, preserving existing rows when provided."""

    rows: List[Dict[str, str]] = list(existing_rows or [])
    new_rows = [product_to_row(p) for p in products]
    rows.extend(new_rows)

    if not rows:
        print("No products to save.")
        return

    active_fieldnames = fieldnames or list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=active_fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Saved {len(rows)} total products to {path} ({len(new_rows)} new)")
