"""CSV export and import utilities."""

import csv
import json
import os
from dataclasses import asdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from scrape.models import Product

__all__ = [
    "load_existing_products",
    "product_to_row",
    "save_products_to_csv",
    "export_db_to_csv",
    "export_category_to_csv",
]


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
    """Convert Product dataclass into a CSV-ready row.
    
    Flattens category_specs into the row with category prefix (e.g., chain_application).
    """
    from scrape.config import get_spec_config

    row = asdict(product)

    # Remove internal fields not needed in CSV
    row.pop("id", None)

    # Flatten category_specs with category prefix
    category_specs = row.pop("category_specs", {}) or {}
    if category_specs:
        # Get prefix from spec table name in CATEGORY_SPECS registry
        spec_config = get_spec_config(product.category)
        if spec_config and "spec_table" in spec_config:
            # Extract prefix from spec_table name (e.g., "chain_specs" -> "chain")
            prefix = spec_config["spec_table"].replace("_specs", "")
        else:
            # Fallback: simple heuristic for unknown categories
            prefix = product.category.rstrip("s")

        for key, value in category_specs.items():
            row[f"{prefix}_{key}"] = value

    # Serialize specs dict to JSON string
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

    # Merge fieldnames to include any new fields (e.g., image_url) while preserving order.
    active_fieldnames = fieldnames or list(rows[0].keys())
    for row in rows:
        for key in row.keys():
            if key not in active_fieldnames:
                active_fieldnames.append(key)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=active_fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Saved {len(rows)} total products to {path} ({len(new_rows)} new)")


# =============================================================================
# Database Export Functions
# =============================================================================

def export_db_to_csv(
    db_path: str,
    csv_path: str,
    category: Optional[str] = None,
    include_category_specs: bool = True,
) -> int:
    """Export products from SQLite database to CSV.
    
    Args:
        db_path: Path to the SQLite database
        csv_path: Path for the output CSV file
        category: Optional category filter
        include_category_specs: Whether to include category-specific fields
        
    Returns:
        Number of products exported
    """
    from scrape.db import get_all_products

    products = get_all_products(db_path, category=category, include_specs=include_category_specs)

    if not products:
        print("No products to export.")
        return 0

    # Build fieldnames: core fields + flattened category specs
    core_fields = [
        "id", "category", "name", "url", "image_url", "brand", "price_text",
        "sku", "breadcrumbs", "description", "specs", "created_at", "updated_at"
    ]

    # Collect all category spec field names
    spec_fields: List[str] = []
    if include_category_specs:
        for product in products:
            if "category_specs" in product and product["category_specs"]:
                for key in product["category_specs"].keys():
                    prefixed_key = f"{product['category']}_{key}"
                    if prefixed_key not in spec_fields:
                        spec_fields.append(prefixed_key)

    fieldnames = core_fields + sorted(spec_fields)

    # Convert products to rows
    rows: List[Dict[str, Any]] = []
    for product in products:
        row: Dict[str, Any] = {}
        for field in core_fields:
            if field == "specs" and product.get("specs"):
                row[field] = json.dumps(product["specs"], ensure_ascii=False)
            else:
                row[field] = product.get(field, "")

        # Flatten category specs with prefix
        if include_category_specs and "category_specs" in product and product["category_specs"]:
            for key, value in product["category_specs"].items():
                prefixed_key = f"{product['category']}_{key}"
                row[prefixed_key] = value if value else ""

        rows.append(row)

    # Write CSV
    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Exported {len(rows)} products to {csv_path}")
    return len(rows)


def export_category_to_csv(
    db_path: str,
    category: str,
    csv_path: str,
) -> int:
    """Export a single category with its specific fields to CSV.
    
    This creates a cleaner CSV with only the fields relevant to that category.
    """
    from scrape.db import get_all_products

    products = get_all_products(db_path, category=category, include_specs=True)

    if not products:
        print(f"No products found for category '{category}'.")
        return 0

    # Determine spec fields for this category
    spec_fields: List[str] = []
    for product in products:
        if "category_specs" in product and product["category_specs"]:
            for key in product["category_specs"].keys():
                if key not in spec_fields:
                    spec_fields.append(key)

    # Core fields (without category since we're exporting a single category)
    core_fields = [
        "id", "name", "url", "image_url", "brand", "price_text",
        "sku", "breadcrumbs", "description"
    ]

    fieldnames = core_fields + sorted(spec_fields)

    # Convert to rows
    rows: List[Dict[str, Any]] = []
    for product in products:
        row: Dict[str, Any] = {field: product.get(field, "") for field in core_fields}

        if "category_specs" in product and product["category_specs"]:
            for key, value in product["category_specs"].items():
                row[key] = value if value else ""

        rows.append(row)

    # Write CSV
    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Exported {len(rows)} {category} products to {csv_path}")
    return len(rows)
