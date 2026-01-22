# Bike Components Web Scraper

A modular Python scraper for extracting product information from [bike-components.de](https://www.bike-components.de).

## Overview

This scraper extracts product details from any bike component category on the site. It's designed with a pragmatic, modular architecture that separates concerns for maintainability and testability.

## Features

### Core Scraping
- **Polite scraping** - Respects rate limits with random delays between requests
- **Overnight mode** - Extra-slow delays (10-30s) for unattended background runs
- **Exponential backoff** - Automatic retries with increasing delays on server errors
- **Session reuse** - HTTP session persistence for efficient connections
- **Graceful shutdown** - Ctrl+C cleanly saves progress (double-press to force quit)
- **Error resilience** - Continues scraping even if individual products fail to parse

### Data Storage & Processing
- **SQLite database** - Normalized storage with separate tables for category-specific specs
- **Dynamic specs system** - Flexible field discovery and storage for any category (no schema changes needed)
- **Type-safe specs** - Proper handling of optional/None values in dynamic specs
- **Multi-category products** - Products can belong to multiple categories without duplication

### Product Discovery & Enhancement
- **Pagination support** - Automatically follows pagination to scrape all products in a category
- **Product images** - Extracts primary product image URL via og:image meta tag
- **Auto-discovery tools** - Discover categories from sitemap and fields from product sampling
- **Automatic field persistence** - Discovered fields are saved to database and reused across scraping sessions
- **Discover-scrape workflow** - Select a parent category, discover subcategories, analyze fields, and scrape all in one command

### Configuration & Flexibility
- **Category spec registry** - Flexible field mapping per category (chains, cassettes, etc.) in [config.py](config.py)
- **Incremental mode (default)** - Skips products already present in the database
- **Full refresh option** - Rescrape everything on demand
- **Robust parsing** - Handles various HTML structures with fallbacks
- **URL validation** - Security checks to prevent SSRF vulnerabilities

### Logging & Debugging
- **Structured logging** - JSONL log files for debugging and auditing
- **HTML data viewer** - Visual inspection of scraped data and category coverage
- **Comprehensive test suite** - Unit tests for dynamic specs, pagination, and field discovery

## Project Structure

```
scrape/
├── __init__.py              # Package initialization with convenient exports
├── config.py                # Configuration, URLs, delays, retry settings, and category spec registry
├── models.py                # Data models (Product dataclass)
├── html_utils.py            # HTML parsing utilities
├── scraper.py               # Core scraping logic with retries and session management
├── db.py                    # SQLite database schema and helpers
├── csv_utils.py             # Deprecated CSV utilities (legacy compatibility)
├── workflows.py             # High-level scraping workflows (discover-scrape)
├── cli.py                   # Command-line interface with verbose/overnight modes
├── discover_fields.py       # Auto-discover spec fields from product sampling
├── discover_categories.py   # Auto-discover categories from sitemap
├── view_data.py             # HTML data viewer for scraped data and category coverage
├── logging_config.py        # Structured JSONL logging with colored console output
├── shutdown.py              # Graceful shutdown signal handling
├── url_validation.py        # URL security validation
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
- `DELAY_MIN` / `DELAY_MAX` - Polite delay range between requests (1-3s default)
- `DELAY_OVERNIGHT_MIN` / `DELAY_OVERNIGHT_MAX` - Slower delays for overnight runs (10-30s)
- `MAX_RETRIES` - Maximum retry attempts on server errors (default: 5)
- `RETRY_BACKOFF_BASE` - Exponential backoff base (default: 2.0)
- `MAX_RETRY_BACKOFF` - Maximum backoff time in seconds (default: 60)
- `RETRY_STATUS_CODES` - HTTP status codes to retry (429, 500, 502, 503, 504)
- `MAX_PAGES_PER_CATEGORY` - Maximum pages to scrape per category (default: 50)
- `DEFAULT_MAX_PAGES` - Default page limit when not specified (default: 10)
- `DB_PATH` - SQLite database path (default: `data/products.db`)

#### `models.py`
`Product` dataclass with fields:
- **Core fields**: `category`, `name`, `url`
- **Product details**: `image_url`, `brand`, `price_text`, `sku`, `breadcrumbs`
- **Description**: `description`, `specs` (raw dict from HTML)
- **Dynamic specs**: `dynamic_specs` (auto-discovered fields stored per product/category)

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
- `map_dynamic_specs()` - Normalizes raw specs into discovered dynamic fields
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
- `init_db()` - Creates tables (products, dynamic_specs, discovered_fields)
- `upsert_product()` - Insert or update product, returns ID
- `upsert_dynamic_specs()` - Insert or update dynamic specs for any category
- `get_dynamic_specs()` / `get_all_dynamic_specs_for_category()` - Retrieve dynamic specs per product or category
- `save_discovered_fields()` / `get_discovered_fields()` - Persist field discovery results per category
- `get_existing_urls()` - Get URLs already in database (for incremental mode)
- `get_all_products()` - Retrieve products with optional category filter

- `update_scrape_state()` / `get_scrape_state()` - Track pagination progress

#### `workflows.py`
High-level orchestration for complex multi-step operations:
- `get_leaf_categories_under_path()` - Find leaf categories under a parent path
- `run_field_discovery_for_category()` - Run field discovery for a category and persist results
- `scrape_dynamic_category()` - Scrape a dynamically discovered category using persisted fields
- `discover_and_scrape_workflow()` - Full workflow: discover → analyze → scrape (field discovery is built-in)

#### `csv_utils.py`
Deprecated CSV utilities (use database directly):
- `load_existing_products()` - Reads existing CSV rows (legacy compatibility only)

#### `cli.py`
Command-line interface:
- `--mode incremental` (default) skips URLs already in database
- `--mode full` forces a complete rescrape
- `--max-pages` limit pages per category (default: 10)
- `--overnight` enables slow mode (10-30s delays) for unattended runs
- `--verbose` enables detailed console logging
- `--discover-scrape <path>` - Discover and scrape all subcategories under a path
- `--skip-field-discovery` - Skip field discovery phase
- `--stats` - Show database statistics
- `--field-sample-size` - Products to sample for field discovery (default: 15)
- `--dry-run` - Preview what would be scraped without executing

#### `logging_config.py`
Structured logging infrastructure:
- JSONL log files for debugging and auditing
- Colored console output for readability
- Log levels: DEBUG, INFO, WARNING, ERROR
- Automatic log rotation by date

#### `shutdown.py`
Graceful shutdown handling:
- SIGINT/SIGTERM signal handlers
- Clean exit after current operation
- Double Ctrl+C for force quit

#### `url_validation.py`
URL security validation:
- HTTPS enforcement
- Domain allowlist checking
- SSRF prevention

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
- Optional `--update-view` flag to regenerate data viewer

#### `view_data.py`
HTML data viewer for scrape status and coverage:
- Generates a standalone HTML report from database and discovery data
- **Overview** - Total products, categories scraped, discovery stats
- **Coverage** - Hierarchical tree showing scraped vs not-scraped categories with counts at each level
- **Categories** - Full category tree from sitemap discovery
- **Scrape Progress** - Per-category pagination progress
- **Data Quality** - Missing fields analysis, duplicate detection
- **Products** - Sample product preview with top brands
- Can be called programmatically via `regenerate_report()` after scraping

## Usage

### Using Makefile (Recommended)

The easiest way to run the scraper is via the Makefile in the project root:

```bash
make help              # Show all available commands
make scrape            # Run incremental scrape (configured categories)
make scrape-full       # Full refresh (ignore existing data)
make refresh-data      # Run incremental scrape and update database

# Pipeline targets (discover → analyze → scrape)
make pipeline SUPER=components/drivetrain MAX_PAGES=5
make pipeline-full SUPER=components/drivetrain  # Full rescrape
make pipeline-overnight SUPER=components        # Slow overnight mode

make discover-fields CAT=cassettes  # Discover fields for a category
```

### Run the scraper directly

```bash
# Incremental scrape (default) - skips existing products
python -m scrape.cli

# Full refresh - rescrape everything
python -m scrape.cli --mode full

# Overnight mode - slow delays (10-30s) for unattended runs
python -m scrape.cli --overnight --max-pages 100

# Verbose logging
python -m scrape.cli --verbose

# Limit pages per category
python -m scrape.cli --max-pages 5

# Show database statistics
python -m scrape.cli --stats
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

### View scrape data and coverage

```bash
# Generate HTML report and open in browser
python -m scrape.view_data --open

# Just regenerate the report (no browser)
python -m scrape.view_data

# Use via Makefile
make view-data
```

The viewer shows:
- **Overview**: Total products, categories, brands
- **Coverage**: Hierarchical tree with scraped/total counts per category branch (e.g., "Drivetrain 12/45")
- **Categories**: Full discovery tree from sitemap
- **Scrape Progress**: Pagination status per category
- **Data Quality**: Missing fields, duplicates, spec table coverage
- **Products**: Sample products and top brands

### Use as a module

The package exports common functions for convenient imports:

```python
# Convenient top-level imports
from scrape import (
    Product,
    scrape_category,
    init_db,
    get_existing_urls,
    discover_and_scrape_workflow,
)

# Or import from specific modules
from scrape.scraper import scrape_category, parse_product_page
from scrape.db import init_db, get_all_products, get_spec_table_for_category
from scrape.workflows import discover_and_scrape_workflow
from scrape.config import CATEGORY_SPECS, get_spec_config

# Initialize database
init_db("data/products.db")

# Scrape a category with pagination (saves to DB automatically)
products = scrape_category(
    "chains",
    "https://www.bike-components.de/en/components/drivetrain/chains/",
    max_pages=5,
    db_path="data/products.db"
)

# Query products from database
from scrape.db import get_all_products
all_products = get_all_products("data/products.db", category="chains")
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

**Dynamic specs table** (`dynamic_specs`):
- `product_id` (foreign key)
- `category` (category key)
- `field_name`, `field_value` (auto-discovered normalized specs)

**Discovered fields table** (`discovered_fields`):
- `category` (category key)
- `field_name` (normalized field name)
- `original_labels` (JSON array of matched labels)
- `frequency` (how often the field appeared in the sample)

### CSV Export

Export produces a flat CSV with columns:
- Core fields: `id`, `category`, `name`, `url`, `image_url`, `brand`, etc.
- Category specs: prefixed with category name (e.g., `chains_application`, `cassettes_gearing`)
- Dynamic specs: prefixed with category key (e.g., `chains_material`, `cassettes_teeth_count`)

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
DELAY_MIN = 1.0           # Normal mode minimum delay
DELAY_MAX = 3.0           # Normal mode maximum delay
DELAY_OVERNIGHT_MIN = 10.0  # Overnight mode minimum delay
DELAY_OVERNIGHT_MAX = 30.0  # Overnight mode maximum delay
REQUEST_TIMEOUT = 15

# Retry settings
MAX_RETRIES = 5           # Max retry attempts on server errors
RETRY_BACKOFF_BASE = 2.0  # Exponential backoff base (2^attempt)
MAX_RETRY_BACKOFF = 60.0  # Cap backoff at 60 seconds
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}  # Status codes to retry

# Pagination limits
MAX_PAGES_PER_CATEGORY = 50
DEFAULT_MAX_PAGES = 10

# Database location
DB_PATH = "data/products.db"
```

## Resilience Features

### Overnight Mode

For long-running unattended scrapes, use overnight mode which uses much slower delays (10-30 seconds between requests instead of 1-3 seconds):

```bash
# Via Makefile
make pipeline-overnight SUPER=components/drivetrain

# Via CLI
python -m scrape.cli --overnight --max-pages 100

# Via environment variable
OVERNIGHT=1 python -m scrape.cli
```

### Automatic Retries with Exponential Backoff

The scraper automatically retries failed requests for recoverable errors (429 rate limiting, 5xx server errors):

- Retry up to 5 times (configurable via `MAX_RETRIES`)
- Wait time doubles each attempt: 2s → 4s → 8s → 16s → 32s...
- Capped at 60 seconds maximum wait (configurable via `MAX_RETRY_BACKOFF`)
- Only retries status codes: 429, 500, 502, 503, 504

### Session Reuse

HTTP sessions are reused across requests for better performance and connection pooling. Sessions maintain:
- Keep-alive connections
- Cookie persistence
- Shared headers

### Graceful Shutdown

Press Ctrl+C once to gracefully stop after the current product finishes:

```
^C
Shutdown requested (press Ctrl+C again to force quit)
Finishing current operation...
```

This ensures:
- Current product is fully processed and saved
- Database connections are properly closed
- No partial data corruption

Press Ctrl+C twice to force immediate termination.

### Structured Logging

All scraper operations are logged to both console (with colors) and a JSONL file for debugging:

```bash
# Enable verbose console output
python -m scrape.cli --verbose

# Logs are saved to scrape/logs/scraper_YYYYMMDD.jsonl
```

Log entries include:
- Timestamp, log level, message
- Category, URL, product details
- Error tracebacks for debugging
- Request timing and retry information

### URL Validation

All URLs are validated before requests to prevent:
- SSRF (Server-Side Request Forgery) attacks
- Requests to non-HTTPS URLs
- Requests outside the allowed domain (bike-components.de)

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
- ✅ Dynamic specs pipeline (auto-discovery, storage, CSV export for all categories)
- ✅ Auto-discover categories from sitemap
- ✅ Auto-discover spec fields via sampling
- ✅ Product image URL extraction
- ✅ Discover-scrape workflow for bulk operations
- ✅ Incremental scraping (skip existing products)
- ✅ CSV export with flattened fields
- ✅ Overnight mode for slow unattended scraping
- ✅ Automatic retries with exponential backoff
- ✅ Session reuse for efficient connections
- ✅ Graceful shutdown (Ctrl+C saves progress)
- ✅ Structured JSONL logging
- ✅ URL validation for security

## Future Enhancements

- [ ] Caching of fetched pages to reduce load
- [ ] Price history tracking
- [ ] Multi-threaded/async scraping
- [ ] Automatic schema generation from discovered fields
- [ ] Resume interrupted scrape sessions
