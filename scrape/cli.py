"""Command-line interface for the scraper."""

import sys
from pathlib import Path
from typing import List

# Add parent directory to path to allow imports when run as script
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrape.config import CATEGORY_URLS, OUTPUT_PATH
from scrape.models import Product
from scrape.scraper import scrape_category
from scrape.csv_utils import save_products_to_csv


def scrape_all() -> List[Product]:
    """Scrape all configured categories and return products."""
    all_products: List[Product] = []
    for category_key, url in CATEGORY_URLS.items():
        products = scrape_category(category_key, url)
        all_products.extend(products)
    return all_products


def main() -> None:
    """Main entry point for CLI."""
    all_products = scrape_all()
    save_products_to_csv(all_products, OUTPUT_PATH)


if __name__ == "__main__":
    main()
