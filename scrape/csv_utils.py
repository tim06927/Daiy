"""CSV export utilities."""

import csv
import json
from dataclasses import asdict
from typing import Iterable

from scrape.models import Product


def save_products_to_csv(products: Iterable[Product], path: str) -> None:
    """Save products to a CSV file."""
    products_list = list(products)
    if not products_list:
        print("No products to save.")
        return

    fieldnames = list(asdict(products_list[0]).keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in products_list:
            row = asdict(p)
            # specs is a dict → serialise to JSON
            if row.get("specs") is not None:
                row["specs"] = json.dumps(row["specs"], ensure_ascii=False)
            writer.writerow(row)

    print(f"Saved {len(products_list)} products to {path}")
