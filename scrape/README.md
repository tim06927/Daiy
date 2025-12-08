# Bike Components Web Scraper

A modular Python scraper for extracting product information from [bike-components.de](https://www.bike-components.de).

## Overview

This scraper extracts product details from bike component categories including cassettes, chains, drivetrain tools, and mountain bike gloves. It's designed with a pragmatic, modular architecture that separates concerns for maintainability and testability.

## Features

- **Polite scraping** - Respects rate limits with random delays between requests
- **Incremental mode (default)** - Skips products already present in the output CSV to avoid re-scraping
- **Full refresh option** - Rescrape everything on demand
- **Robust parsing** - Handles various HTML structures with fallbacks
- **Structured data** - Exports products to CSV with normalized fields
- **Category-specific fields** - Special handling for chain products with normalized specs (application, gearing, number of links, closure type, pin type, directionality, material)
- **Error resilience** - Continues scraping even if individual products fail to parse

## Project Structure

```
scrape/
├── __init__.py          # Package initialization
├── config.py            # Configuration, constants, and URLs
├── models.py            # Data models (Product dataclass)
├── html_utils.py        # HTML parsing utilities
├── scraper.py           # Core scraping logic
├── csv_utils.py         # CSV export utilities
├── cli.py               # Command-line interface
└── README.md            # This file
```

### Module Responsibilities

#### `config.py`
Centralized configuration:
- `BASE_URL` - Base domain for bike-components.de
- `CATEGORY_URLS` - Dictionary mapping category keys to scrape URLs
- `HEADERS` - HTTP headers for polite user-agent identification
- `REQUEST_TIMEOUT` - HTTP request timeout in seconds
- `DELAY_MIN` / `DELAY_MAX` - Polite delay range between requests
- `OUTPUT_PATH` - Default CSV output file path

#### `models.py`
`Product` dataclass with fields:
- **Core fields**: `category`, `name`, `url`
- **Product details**: `brand`, `price_text`, `sku`, `breadcrumbs`
- **Description**: `description`, `specs` (dict)
- **Chain-specific** (chains category only): `chain_application`, `chain_gearing`, `chain_num_links`, `chain_closure_type`, `chain_pin_type`, `chain_directional`, `chain_material`

#### `html_utils.py`
HTML parsing and data extraction utilities:
- `extract_sku()` - Extracts product SKU/item number
- `extract_breadcrumbs()` - Extracts breadcrumb navigation path
- `extract_description_and_specs()` - Parses product description and specification lists
- `pick_spec()` - Finds specs by key with case-insensitive fallback
- `map_chain_specs()` - Normalizes chain-specific specifications
- `is_product_url()` - Validates product page URLs

#### `scraper.py`
Core scraping orchestration:
- `fetch_html()` - Polite HTTP GET with delays
- `extract_product_links()` - Finds product URLs on category pages
- `parse_product_page()` - Parses individual product HTML into Product object
- `scrape_category()` - Orchestrates scraping a single category, with optional skipping of already-seen URLs

#### `csv_utils.py`
Data export/import:
- `load_existing_products()` - Reads existing CSV rows and header
- `product_to_row()` - Converts `Product` to a CSV row (JSON-serializes specs)
- `save_products_to_csv()` - Exports products to CSV and can preserve existing rows

#### `cli.py`
Command-line interface:
- `--mode incremental` (default) skips URLs already in the output CSV
- `--mode full` forces a complete rescrape
- `--output` overrides the CSV path
- `scrape_all()` - Scrapes all configured categories respecting the mode
- `main()` - Entry point that orchestrates scrape and export

## Usage

### Run the scraper

```bash
python scrape/cli.py                  # incremental (default)
python scrape/cli.py --mode full      # full refresh (ignore existing CSV)
python scrape/cli.py --output path.csv
```

Incremental mode will skip any product URLs already present in the output CSV. Full mode ignores the CSV and rewrites it with freshly scraped data.

### Use as a module

```python
from scrape.scraper import scrape_category
from scrape.csv_utils import save_products_to_csv

# Scrape a single category
products = scrape_category("chains", "https://www.bike-components.de/en/components/drivetrain/chains/")

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
```

2. Run the scraper - it will automatically scrape the new category

### Add category-specific field mappings

Modify `scraper.py`'s `parse_product_page()` function to add normalized fields for new categories, similar to chain handling.

## Output Format

The scraper produces a CSV with these columns:
- `category` - Product category
- `name` - Product name
- `url` - Product detail URL
- `brand` - Brand/manufacturer
- `price_text` - Price as displayed on site
- `sku` - Stock-keeping unit / item number
- `breadcrumbs` - Navigation breadcrumb path
- `description` - Full product description
- `specs` - JSON-encoded specification key-value pairs
- `chain_*` fields (if applicable) - Normalized chain specifications

## Configuration

Edit `config.py` to customize:

```python
# Add/remove categories
CATEGORY_URLS = {...}

# Adjust request timing
DELAY_MIN = 1.0
DELAY_MAX = 3.0
REQUEST_TIMEOUT = 15

# Change output location
OUTPUT_PATH = "data/my_output.csv"
```

## Design Philosophy

- **Modular**: Each function has a single responsibility
- **Pragmatic**: Balanced between simplicity and robustness
- **Testable**: Utilities are pure functions where possible
- **Extensible**: Easy to add new categories or parsing logic
- **Respectful**: Includes polite delays and proper user-agent identification

## Current Limitations

- Only scrapes the first page of results per category (pagination not yet implemented)
- No persistent caching of fetched pages
- No database storage (CSV export only)

## Future Enhancements

- [ ] Pagination support for large categories
- [ ] Database storage (SQLite or PostgreSQL)
- [ ] Caching of fetched pages to reduce load
- [ ] Price history tracking
- [ ] Multi-threaded/async scraping
- [ ] CLI with arguments for category selection and output format
