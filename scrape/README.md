# Bike Components Web Scraper

A modular Python scraper for extracting product information from [bike-components.de](https://www.bike-components.de).

## Overview

This scraper extracts product details from bike component categories including cassettes, chains, drivetrain tools, and mountain bike gloves. It's designed with a pragmatic, modular architecture that separates concerns for maintainability and testability.

## Features

- **Polite scraping** - Respects rate limits with random delays between requests
- **Pagination support** - Automatically follows pagination to scrape all products in a category
- **SQLite database** - Normalized storage with separate tables for category-specific specs
- **Incremental mode (default)** - Skips products already present in the database
- **Full refresh option** - Rescrape everything on demand
- **Robust parsing** - Handles various HTML structures with fallbacks
- **Product images** - Extracts primary product image URL via og:image meta tag
- **Category spec registry** - Flexible field mapping per category (chains, cassettes, etc.)
- **Auto-discovery tools** - Discover categories from sitemap and fields from product sampling
- **Discover-scrape workflow** - Select a parent category, discover subcategories, analyze fields, and scrape all in one command
- **CSV export** - Export database to CSV with flattened category-specific fields
- **Error resilience** - Continues scraping even if individual products fail to parse

## Project Structure

```
scrape/
├── __init__.py              # Package initialization with convenient exports
├── config.py                # Configuration, URLs, and category spec registry
├── models.py                # Data models (Product dataclass)
├── html_utils.py            # HTML parsing utilities
├── scraper.py               # Core scraping logic
├── db.py                    # SQLite database schema and helpers
├── csv_utils.py             # CSV export utilities
├── workflows.py             # High-level scraping workflows (discover-scrape)
├── cli.py                   # Command-line interface
├── discover_fields.py       # Auto-discover spec fields from product sampling
├── discover_categories.py   # Auto-discover categories from sitemap
└── README.md                # This file
```

### Module Responsibilities

#### `config.py`
Centralized configuration:
- `BASE_URL` - Base domain for bike-components.de
- `CATEGORY_URLS` - Dictionary mapping category keys to scrape URLs
- `CATEGORY_SPECS` - Registry mapping categories to spec tables and field mappings
- `HEADERS` - HTTP headers for polite user-agent identification
- `REQUEST_TIMEOUT` - HTTP request timeout in seconds
- `DELAY_MIN` / `DELAY_MAX` - Polite delay range between requests
- `MAX_PAGES_PER_CATEGORY` - Maximum pages to scrape per category (default: 50)
- `DEFAULT_MAX_PAGES` - Default page limit when not specified (default: 10)
- `DB_PATH` - SQLite database path (default: `data/products.db`)

#### `models.py`
`Product` dataclass with fields:
- **Core fields**: `category`, `name`, `url`
- **Product details**: `image_url`, `brand`, `price_text`, `sku`, `breadcrumbs`
- **Description**: `description`, `specs` (raw dict from HTML)
- **Category specs**: `category_specs` (normalized dict for DB storage)

#### `html_utils.py`
HTML parsing and data extraction utilities:
- `extract_sku()` - Extracts product SKU/item number
- `extract_breadcrumbs()` - Extracts breadcrumb navigation path
- `extract_description_and_specs()` - Parses product description and specification lists
- `extract_primary_image_url()` - Extracts main product image (og:image, gallery, JSON-LD)
- `extract_next_page_url()` - Finds next page URL for pagination
- `extract_current_page()` / `extract_total_pages()` - Pagination helpers
- `pick_spec()` - Finds specs by key with case-insensitive fallback
- `map_category_specs()` - Generic spec mapping using category registry
- `is_product_url()` - Validates product page URLs

#### `scraper.py`
Core scraping orchestration:
- `fetch_html()` - Polite HTTP GET with delays
- `extract_product_links()` - Finds product URLs on category pages
- `parse_product_page()` - Parses individual product HTML into Product object
- `scrape_category()` - Orchestrates scraping with pagination and DB storage
- `save_product_to_db()` - Saves product to SQLite database

#### `db.py`
SQLite database schema and helpers:
- `init_db()` - Creates tables (products, chain_specs, cassette_specs, etc.)
- `upsert_product()` - Insert or update product, returns ID
- `upsert_category_specs()` - Insert or update category-specific specs
- `get_existing_urls()` - Get URLs already in database (for incremental mode)
- `get_all_products()` - Retrieve products with optional category filter
- `get_spec_table_for_category()` - Maps category to spec table (uses `CATEGORY_SPECS` from config.py)
- `update_scrape_state()` / `get_scrape_state()` - Track pagination progress

#### `workflows.py`
High-level orchestration for complex multi-step operations:
- `get_leaf_categories_under_path()` - Find leaf categories under a parent path
- `run_field_discovery_for_category()` - Run field discovery for a category
- `scrape_dynamic_category()` - Scrape a dynamically discovered category
- `discover_and_scrape_workflow()` - Full workflow: discover → analyze → scrape

#### `csv_utils.py`
Data export/import:
- `load_existing_products()` - Reads existing CSV rows and header
- `product_to_row()` - Converts `Product` to CSV row (flattens category_specs with prefix)
- `save_products_to_csv()` - Exports products to CSV
- `export_db_to_csv()` - Export database to CSV with flattened category specs
- `export_category_to_csv()` - Export single category to CSV

#### `cli.py`
Command-line interface:
- `--mode incremental` (default) skips URLs already in database
- `--mode full` forces a complete rescrape
- `--output` overrides the CSV path
- `--max-pages` limit pages per category (default: 10)
- `--discover-scrape <path>` - Discover and scrape all subcategories under a path
- `--skip-field-discovery` - Skip field discovery phase
- `--field-sample-size` - Products to sample for field discovery (default: 15)
- `--dry-run` - Preview what would be scraped without executing

#### `discover_fields.py`
Field discovery tool:
- Samples products from a category
- Analyzes spec field frequency
- Suggests schema for new categories

#### `discover_categories.py`
Category discovery tool:
- Fetches sitemap from bike-components.de
- Parses category URLs and builds hierarchy
- Identifies leaf categories for scraping

## Usage

### Using Makefile (Recommended)

The easiest way to run the scraper is via the Makefile in the project root:

```bash
make help              # Show all available commands
make scrape            # Run incremental scrape (configured categories)
make scrape-full       # Full refresh (ignore existing data)
make refresh-data      # Scrape + export CSV + show git diff
make export            # Export database to CSV
make scrape-drivetrain MAX_PAGES=3  # Scrape drivetrain subcategories
make discover-fields CAT=cassettes  # Discover fields for a category
```

### Run the scraper directly

```bash
# Incremental scrape (default) - skips existing products
python -m scrape.cli

# Full refresh - rescrape everything
python -m scrape.cli --mode full

# Limit pages per category
python -m scrape.cli --max-pages 5

# Custom output CSV
python -m scrape.cli --output path.csv
```

### Discover-scrape workflow

Automatically discover and scrape all subcategories under a parent category:

```bash
# Preview what would be scraped (dry run)
python -m scrape.cli --discover-scrape components/drivetrain --dry-run

# Discover fields and scrape all subcategories
python -m scrape.cli --discover-scrape components/drivetrain --max-pages 2

# Skip field discovery, just scrape with existing config
python -m scrape.cli --discover-scrape accessories/lighting --skip-field-discovery

# Custom field sample size
python -m scrape.cli --discover-scrape components/drivetrain --field-sample-size 30
```

### Discovery tools

```bash
# Discover categories from sitemap
python -m scrape.discover_categories --filter components
python -m scrape.discover_categories --output data/categories.json

# Discover spec fields for a category
python -m scrape.discover_fields cassettes --sample-size 20
python -m scrape.discover_fields chains --threshold 0.3
```

### Export database to CSV

```bash
# Export all products
python -m scrape.csv_utils --export data/products.csv

# Export specific category
python -m scrape.csv_utils --export data/chains.csv --category chains
```

### Use as a module

The package exports common functions for convenient imports:

```python
# Convenient top-level imports
from scrape import (
    Product,
    scrape_category,
    init_db,
    get_existing_urls,
    export_db_to_csv,
    discover_and_scrape_workflow,
)

# Or import from specific modules
from scrape.scraper import scrape_category, parse_product_page
from scrape.db import init_db, get_all_products, get_spec_table_for_category
from scrape.csv_utils import export_db_to_csv, product_to_row
from scrape.workflows import discover_and_scrape_workflow
from scrape.config import CATEGORY_SPECS, get_spec_config

# Initialize database
init_db("data/products.db")

# Scrape a category with pagination (saves to DB)
products = scrape_category(
    "chains",
    "https://www.bike-components.de/en/components/drivetrain/chains/",
    max_pages=5,
    use_db=True,
    db_path="data/products.db"
)

# Export to CSV
export_db_to_csv("data/products.db", "output.csv", category="chains")
```

# Save to CSV
save_products_to_csv(products, "output.csv")
```

### Extend for new categories

1. Add to `config.py`:
```python
CATEGORY_URLS = {
    "your_category": "https://www.bike-components.de/path/to/category/",
    ...
}

# Add spec mapping (optional, for category-specific fields)
CATEGORY_SPECS = {
    "your_category": {
        "spec_table": "your_category_specs",
        "field_mappings": {
            "db_column": ["Possible Label 1", "Alt Label"],
            "another_column": ["Label"],
        }
    },
    ...
}
```

2. Create the spec table in `db.py` (if using category-specific fields):
```python
cursor.execute("""
    CREATE TABLE IF NOT EXISTS your_category_specs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER UNIQUE NOT NULL,
        db_column TEXT,
        another_column TEXT,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    )
""")
```

3. Run the scraper - it will automatically scrape the new category

### Auto-discover fields for a new category

Use the field discovery tool to analyze what specs are available:

```bash
python -m scrape.discover_fields your_category --sample-size 20
```

This will sample products and show field frequency, helping you decide which fields to add to the schema.

## Output Format

### SQLite Database (Primary)

The scraper stores data in `data/products.db` with normalized tables:

**products** (core table):
- `id`, `category`, `name`, `url`, `image_url`
- `brand`, `price_text`, `sku`, `breadcrumbs`
- `description`, `specs_json`
- `created_at`, `updated_at`

**Category-specific tables** (e.g., `chain_specs`, `cassette_specs`):
- `product_id` (foreign key)
- Category-specific columns (application, gearing, etc.)

### CSV Export

Export produces a flat CSV with columns:
- Core fields: `id`, `category`, `name`, `url`, `image_url`, `brand`, etc.
- Category specs: prefixed with category name (e.g., `chains_application`, `cassettes_gearing`)

## Configuration

Edit `config.py` to customize:

```python
# Add/remove categories
CATEGORY_URLS = {...}

# Category-specific field mappings
CATEGORY_SPECS = {
    "chains": {
        "spec_table": "chain_specs",
        "field_mappings": {
            "application": ["Application", "Intended Use"],
            "gearing": ["Gearing", "Number of Speeds"],
            ...
        }
    },
    ...
}

# Adjust request timing
DELAY_MIN = 1.0
DELAY_MAX = 3.0
REQUEST_TIMEOUT = 15

# Pagination limits
MAX_PAGES_PER_CATEGORY = 50
DEFAULT_MAX_PAGES = 10

# Database location
DB_PATH = "data/products.db"
```

## Design Philosophy

- **Modular**: Each function has a single responsibility
- **Pragmatic**: Balanced between simplicity and robustness
- **Testable**: Utilities are pure functions where possible
- **Extensible**: Easy to add new categories via registry pattern
- **Respectful**: Includes polite delays and proper user-agent identification
- **Data-first**: SQLite for structured storage, CSV for easy export

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│  discover_      │     │   cli.py     │     │  csv_utils  │
│  categories.py  │────▶│   (main)     │────▶│  (export)   │
└─────────────────┘     └──────┬───────┘     └─────────────┘
                               │
┌─────────────────┐            ▼
│  discover_      │     ┌──────────────┐
│  fields.py      │────▶│  scraper.py  │
└─────────────────┘     └──────┬───────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  html_utils  │
                        └──────┬───────┘
                               │
                               ▼
                        ┌──────────────┐
                        │    db.py     │
                        │   (SQLite)   │
                        └──────────────┘
```

## Current Capabilities

- ✅ Pagination support for large categories
- ✅ SQLite database storage with normalized schema
- ✅ Category-specific spec tables (chains, cassettes, gloves, tools)
- ✅ Auto-discover categories from sitemap
- ✅ Auto-discover spec fields via sampling
- ✅ Product image URL extraction
- ✅ Discover-scrape workflow for bulk operations
- ✅ Incremental scraping (skip existing products)
- ✅ CSV export with flattened fields

## Future Enhancements

- [ ] Caching of fetched pages to reduce load
- [ ] Price history tracking
- [ ] Multi-threaded/async scraping
- [ ] Automatic schema generation from discovered fields
- [ ] Resume interrupted scrape sessions
