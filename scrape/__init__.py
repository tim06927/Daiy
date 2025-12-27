"""Bike Components web scraper package."""

__version__ = "0.1.0"

# Re-export main components for convenient imports
from scrape.config import (
    BASE_URL,
    CATEGORY_SPECS,
    CATEGORY_URLS,
    DB_PATH,
    get_spec_config,
)
from scrape.csv_utils import export_db_to_csv
from scrape.db import get_existing_urls, get_product_count, init_db
from scrape.models import Product
from scrape.scraper import scrape_category
from scrape.workflows import discover_and_scrape_workflow

__all__ = [
    # Version
    "__version__",
    # Config
    "BASE_URL",
    "CATEGORY_SPECS",
    "CATEGORY_URLS",
    "DB_PATH",
    "get_spec_config",
    # Models
    "Product",
    # Core functions
    "scrape_category",
    "init_db",
    "get_existing_urls",
    "get_product_count",
    "export_db_to_csv",
    "discover_and_scrape_workflow",
]
