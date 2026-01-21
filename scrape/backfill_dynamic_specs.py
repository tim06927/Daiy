"""Backfill discovered fields and dynamic specs from existing DB data.

This utility analyzes existing products' raw specs in the database to derive
common fields per category, saves them to the discovered_fields table, and
writes normalized dynamic specs for each product without re-scraping.
"""

import argparse
import json
from collections import Counter, defaultdict
from typing import Any, Dict, List, Tuple

from scrape.db import (
    DEFAULT_DB_PATH,
    get_connection,
    init_db,
    save_discovered_fields,
    upsert_dynamic_specs,
)
from scrape.discover_fields import to_snake_case
from scrape.html_utils import map_dynamic_specs


def _load_products_with_specs(db_path: str) -> Dict[str, List[Tuple[int, Dict[str, str]]]]:
    """Load products that have raw specs, grouped by category."""
    data: Dict[str, List[Tuple[int, Dict[str, str]]]] = {}
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, category, specs_json
            FROM products
            WHERE specs_json IS NOT NULL
            """
        )
        for row in cursor.fetchall():
            try:
                specs = json.loads(row["specs_json"]) if row["specs_json"] else {}
            except json.JSONDecodeError:
                specs = {}
            data.setdefault(row["category"], []).append((row["id"], specs))
    return data


def _discover_fields_from_specs(
    products: List[Tuple[int, Dict[str, str]]],
    min_frequency: float,
) -> List[Dict[str, Any]]:
    """Derive discovered_fields records from existing specs."""
    if not products:
        return []

    label_counter: Counter[str] = Counter()
    label_values: defaultdict[str, List[str]] = defaultdict(list)

    for _, specs in products:
        if not isinstance(specs, dict):
            continue
        for label, value in specs.items():
            label_counter[label] += 1
            if len(label_values[label]) < 3 and value:
                label_values[label].append(value)

    total = len(products)
    fields: List[Dict[str, Any]] = []
    for label, count in label_counter.items():
        freq = count / total if total else 0
        if freq >= min_frequency:
            fields.append(
                {
                    "field_name": to_snake_case(label),
                    "original_labels": [label],
                    "frequency": freq,
                    "sample_values": label_values[label],
                }
            )

    fields.sort(key=lambda f: f["frequency"], reverse=True)
    return fields


def backfill_dynamic_specs(db_path: str, min_frequency: float = 0.3) -> None:
    init_db(db_path)
    products_by_category = _load_products_with_specs(db_path)
    if not products_by_category:
        print("No products with specs_json found; nothing to backfill.")
        return

    print(f"Found {len(products_by_category)} categories with specs to backfill.")

    total_fields = 0
    total_products = 0
    for category, products in products_by_category.items():
        if not products:
            continue

        fields = _discover_fields_from_specs(products, min_frequency)
        if fields:
            save_discovered_fields(db_path, category, fields)
        print(
            f"Category: {category} — products: {len(products)}, "
            f"fields saved: {len(fields)}"
        )

        for product_id, specs in products:
            dynamic = map_dynamic_specs(specs, fields)
            if dynamic:
                upsert_dynamic_specs(db_path, product_id, category, dynamic)
                total_products += 1
        total_fields += len(fields)

    print("\nBackfill complete:")
    print(f"  Categories processed: {len(products_by_category)}")
    print(f"  Discovered fields saved: {total_fields}")
    print(f"  Products with dynamic specs written: {total_products}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill dynamic specs from existing DB data")
    parser.add_argument(
        "--db",
        dest="db_path",
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--min-frequency",
        type=float,
        default=0.3,
        help="Minimum field frequency (0-1) to include in discovered fields (default: 0.3)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    backfill_dynamic_specs(args.db_path, min_frequency=args.min_frequency)


if __name__ == "__main__":
    main()
