"""Command-line interface for the scraper."""

import argparse
import sys
from pathlib import Path
from typing import List, Set

# Add parent directory to path to allow imports when run as script
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrape.config import CATEGORY_URLS, OUTPUT_PATH
from scrape.models import Product
from scrape.scraper import scrape_category
from scrape.csv_utils import (
    load_existing_products,
    save_products_to_csv,
)


def scrape_all(existing_urls: Set[str], force_refresh: bool) -> List[Product]:
    """Scrape all configured categories and return new products."""
    all_products: List[Product] = []
    for category_key, url in CATEGORY_URLS.items():
        products = scrape_category(
            category_key,
            url,
            existing_urls=existing_urls,
            force_refresh=force_refresh,
        )
        # Update the shared set so later categories also skip duplicates
        for p in products:
            existing_urls.add(p.url)
        all_products.extend(products)
    return all_products


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bike-components scraper")
    parser.add_argument(
        "--mode",
        choices=["incremental", "full"],
        default="incremental",
        help="incremental: skip URLs already in the output CSV (default); full: rescrape everything",
    )
    parser.add_argument(
        "--output",
        default=OUTPUT_PATH,
        help=f"Output CSV path (default: {OUTPUT_PATH})",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point for CLI."""
    args = parse_args()
    force_refresh = args.mode == "full"

    existing_rows, existing_fieldnames = ([], [])
    existing_urls: Set[str] = set()

    if not force_refresh:
        existing_rows, existing_fieldnames = load_existing_products(args.output)
        existing_urls = {row.get("url") for row in existing_rows if row.get("url")}

    new_products = scrape_all(existing_urls, force_refresh)

    # Combine and save, preserving existing rows when incremental
    save_products_to_csv(
        new_products,
        args.output,
        existing_rows=None if force_refresh else existing_rows,
        fieldnames=existing_fieldnames,
    )


if __name__ == "__main__":
    main()
