# Daiy

## New in Version 0.3.0

**AI-Powered Product Recommendations with Comprehensive Logging & Monitoring**

This release brings together a complete, alpha-ready system with robust logging, error tracking, and memory-optimized deployment:

### Key Capabilities
- ✅ All clarification questions are **dynamic** and **LLM-generated**
- ✅ **Multi-category products** - No duplicates or missing items
- ✅ **Comprehensive logging** - User inputs, clarifications, LLM calls/responses, errors tracked
- ✅ **Error tracking** - Persistent SQLite error logs with recovery suggestions
- ✅ **Interaction logging** - Full event trace for debugging and monitoring
- ✅ **HTML log viewer** - Interactive session browser with filters
- ✅ **Modular frontend** - Separate concerns for easy maintenance
- ✅ **Vision-enabled** - Image upload for bike photo analysis
- ✅ **Grounded recommendations** - Only real products, no hallucinations
- ✅ **Database-backed** - SQLite for memory efficiency (<200MB RAM)
- ✅ **Real-time updates** - Scraper → Database → Web app (no restart needed)

### Persistent Database Logging
- ✅ **Consolidated SQLite logging** - Single database for products, errors, AND interactions
- ✅ **Persistent across redeployments** - All logs survive Render updates
- ✅ **Full request tracing** - All events (user_input, LLM calls, recommendations) linked via request_id
- ✅ **Interactive log viewer** - Query logs from database with HTML interface
- ✅ **Production-ready monitoring** - Error tracking + interaction logging for full visibility

### Error Tracking System
- ✅ **5 error types** - llm_error, validation_error, database_error, processing_error, unexpected_error
- ✅ **Recovery suggestions** - Actionable guidance for each error
- ✅ **Stack trace capture** - Full traceback for debugging
- ✅ **Request correlation** - Errors linked to user inputs via request_id

### Interaction Logging
- ✅ **All events logged** - user_input, clarification_required, llm_calls, recommendations, performance_metrics
- ✅ **Complete request trace** - Query entire interaction flow for debugging
- ✅ **Local + Remote** - JSONL for development, SQLite for production (Render)
- ✅ **Queryable** - Filter by request_id, event_type, or view all interactions

### Memory Optimization
- ✅ **SQLite database backend** - Replaced 500MB CSV loading with on-demand queries
- ✅ **75% memory reduction** - From 800MB+ to <200MB (fits Render 512MB tier)
- ✅ **Real-time pipeline** - Scraper → Database → Web app (no restart needed)
- ✅ **Removed heavy dependencies** - numpy, psycopg2, pillow-heif, openpyxl
- ✅ **Image optimization** - Convert images to PNG format while preserving full quality

### Backend Enhancements
- ✅ **Fixed type invariance in dynamic specs** - Proper handling of `Mapping[str, Optional[str]]` for flexible product field storage
- ✅ **Robust None-value filtering** - Dynamic specs system skips None values internally, simplifying call sites
- ✅ **Type-safe imports** - All functions properly annotated with Mapping types for covariance
- ✅ **Performance timing & analytics** - Track LLM vs app latency breakdown for optimization

### Three-Phase LLM Flow
1. **Job Identification** - Generates step-by-step instructions with `[category_key]` placeholders
2. **Clarification** - LLM-generated questions for specs with confidence < 0.8
3. **Recommendation** - Replaces placeholders with real products and provides reasoning

### Frontend: Modular Architecture
Restructured monolithic 2200-line `index.html` into 11 maintainable files:
- **3 CSS modules** - base, components, products (1567 lines total)
- **8 JavaScript modules** - config, state, utils, image, api, clarification, products, main (1399 lines total)
- **Clean HTML template** - 180 lines (92% reduction)

### Quality & Testing
- ✅ **Comprehensive test suite** - Web (18+ tests) and scraper (11+ tests) with fixtures
- ✅ **Dynamic field discovery** - Automatic field detection from product data
- ✅ **Multi-category support** - Products belong to multiple categories with proper deduplication
- ✅ **Logging & debugging** - SQLite + JSONL logs with HTML viewers for all interactions and errors

### For Developers
- Backend flow: [web/README.md](web/README.md) | [web/FLOW.md](web/FLOW.md)
- Frontend architecture: [web/static/README.md](web/static/README.md)
- Scraper docs: [scrape/README.md](scrape/README.md)
- **Pipeline flow**: [PIPELINE.md](PIPELINE.md) - Scraper to web app integration
- **Performance & memory**: See [web/README.md](web/README.md#performance-tracking) and [web/README.md](web/README.md#memory-optimization)
- **Error tracking**: [web/README.md](web/README.md#error-tracking--monitoring) - Production error monitoring
- **Interaction logging**: [web/README.md](web/README.md#interaction-logging) - LLM workflow audit trail
- **Render deployment**: [RENDER_ERROR_LOGS.md](RENDER_ERROR_LOGS.md) - Remote error monitoring

---

## About Daiy

A proof-of-concept system demonstrating **multimodal AI-powered product recommendations** grounded in real inventory data.

**Mission:** Help DIYers find the right parts and tools for their projects using intelligent clarification and grounded LLM recommendations.

## Project Overview

This repository contains a **production-ready three-phase LLM system** for generating personalized product recommendations:

```
User Query + Optional Image
           ↓
┌─────────────────────────────────────────────┐
│ Phase 1: Job Identification (LLM)          │
│ • Parse user's project requirements        │
│ • Generate step-by-step instructions       │
│ • Flag uncertain specifications            │
└─────────────────────────────────────────────┘
           ↓
    ┌──────────────┐
    │ Clarify?     │
    └──────────────┘
      ↙            ↘
    No              Yes
    ↓               ↓
  Skip      ┌─────────────────────────────────────────────┐
            │ Phase 2: Dynamic Clarification (LLM+UI)     │
            │ • LLM generates targeted questions         │
            │ • Ask user specs with confidence < 0.8     │
            │ • Collect all answers in one interaction   │
            └─────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────┐
│ Phase 3: Grounded Recommendation (LLM)      │
│ • Filter real products from inventory       │
│ • Replace placeholders with product names   │
│ • Provide per-product reasoning            │
└─────────────────────────────────────────────┘
           ↓
    📊 Display Results
    • Final instructions with product names
    • Primary products (what user needs)
    • Required tools
    • Optional extras (max 3)
    • Per-item explanations
```

**Key Principle:** All recommendations use actual products from the inventory database; no hallucinations.

The system is:
- **Multimodal** - Accepts text queries and optional bike photos for visual analysis
- **Generalized** - LLM prompts are neutral to domain (not hardcoded to bikes)
- **Observable** - Comprehensive JSONL logging of all user interactions and LLM calls
- **Maintainable** - Clear separation of concerns with focused, well-documented modules
- **Type-Safe** - Proper handling of optional values in dynamic specs using Mapping types

## Project Structure

```
├── web/                # Flask web app (main application)
│   ├── app.py          # Flask application with LLM integration
│   ├── config.py       # Centralized configuration
│   ├── static/         # Frontend assets (NEW - modular structure)
│   │   ├── css/        # Stylesheets
│   │   │   ├── base.css        # Variables, resets, layout
│   │   │   ├── components.css  # Forms, buttons, panels
│   │   │   └── products.css    # Product cards, categories
│   │   ├── js/         # JavaScript modules
│   │   │   ├── config.js       # Constants
│   │   │   ├── state.js        # State management
│   │   │   ├── image.js        # Image handling
│   │   │   ├── api.js          # Backend communication
│   │   │   ├── clarification.js # Clarification UI
│   │   │   ├── products.js     # Product rendering
│   │   │   └── main.js         # Initialization
│   │   └── README.md   # Frontend architecture guide
│   ├── templates/      # HTML templates
│   │   └── index.html  # Clean HTML (153 lines, down from 2199)
│   ├── logs/           # LLM interaction logs (JSONL)
│   └── README.md       # Web app documentation
├── scrape/             # Web scraper for bike-components.de
│   ├── __init__.py              # Package init with convenient exports
│   ├── cli.py                   # Command-line interface
│   ├── scraper.py               # Core scraping logic with retries
│   ├── db.py                    # SQLite database schema and helpers
│   ├── html_utils.py            # HTML parsing and dynamic specs mapping
│   ├── models.py                # Data models (Product dataclass)
│   ├── config.py                # Configuration, URLs, delays, retry settings
│   ├── csv_utils.py             # CSV export/import
│   ├── workflows.py             # High-level scraping workflows (discover-scrape)
│   ├── discover_fields.py       # Auto-discover spec fields from products
│   ├── discover_categories.py   # Auto-discover categories from sitemap
│   ├── backfill_dynamic_specs.py # Populate dynamic specs for existing products
│   ├── view_data.py             # HTML data viewer for scrape status
│   ├── logging_config.py        # Structured JSONL logging
│   ├── shutdown.py              # Graceful shutdown signal handling
│   ├── url_validation.py        # URL security validation
│   ├── tests/                   # Test suite for scraper
│   │   ├── test_dynamic_specs.py       # Type-safe dynamic specs tests
│   │   └── test_pagination_extraction.py
│   ├── logs/                    # Scraper operation logs (JSONL)
│   └── README.md                # Scraper documentation
```

## Key Features

### Web App (`web/`) - Main Application

Modern split-panel interface for AI-powered bike component recommendations:
- **Natural language input** - Describe your upgrade project in plain text
- **Image upload** - Optional bike photo for visual analysis
- **Smart clarification** - AI infers speed/use-case or asks targeted questions with hints
- **Grounded results** - Only recommends real products from inventory
- **Per-product explanations** - Each product shows why it fits your needs
- **Tabbed interface** - Products and installation instructions in separate tabs
- **Direct links** - One-click access to bike-components.de product pages

```bash
# Quick start
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
python web/app.py
# Visit http://127.0.0.1:5000
```

### Web Scraping (`scrape/`)

Modular scraper for bike-components.de with SQLite storage:
- **Polite scraping** - Respects rate limits with random delays
- **Overnight mode** - Extra-slow delays (10-30s) for unattended runs
- **Automatic retries** - Exponential backoff on server errors (429, 5xx)
- **Graceful shutdown** - Ctrl+C cleanly saves progress
- **Pagination support** - Automatically follows all pages in a category
- **SQLite database** - Normalized storage with category-specific spec tables
- **Product images** - Extracts primary product image URLs
- **Incremental mode** - Only scrapes new products (default)
- **Auto-discovery** - Discover categories from sitemap, fields from sampling
- **Discover-scrape workflow** - Bulk scrape entire category trees
- **Data viewer** - HTML report showing scrape coverage and data quality
- **Structured logging** - JSONL logs for debugging and auditing
- **URL validation** - Security checks to prevent SSRF attacks
- **Category support** - Cassettes, chains, drivetrain tools, gloves, and more

```bash
# Run incremental scrape (skip existing)
python -m scrape.cli

# Full refresh with pagination limit
python -m scrape.cli --mode full --max-pages 5

# Overnight mode - slow delays for unattended runs
python -m scrape.cli --overnight --max-pages 100

# Verbose logging
python -m scrape.cli --verbose

# Discover and scrape all drivetrain subcategories
python -m scrape.cli --discover-scrape components/drivetrain --dry-run
python -m scrape.cli --discover-scrape components/drivetrain --max-pages 2

# Discover categories from sitemap
python -m scrape.discover_categories --filter components

# Discover spec fields for a category
python -m scrape.discover_fields cassettes --sample-size 20
```

## Makefile Commands

A `Makefile` is provided for common tasks:

```bash
make help              # Show all available commands
make run               # Start the Flask web app
make refresh-data      # Scrape → export CSV → show git diff
make scrape            # Run incremental scrape
make export            # Export database to CSV
make discover-fields CAT=cassettes  # Discover fields for a category

# Pipeline targets (discover → analyze → scrape a parent category)
make pipeline SUPER=components/drivetrain MAX_PAGES=5
make pipeline-full SUPER=components/drivetrain  # Full rescrape
make pipeline-overnight SUPER=components        # Slow overnight mode
```

**Key workflows:**
- `make refresh-data` - Update product data and prepare for commit
- `make pipeline SUPER=components/drivetrain` - Discover and scrape all subcategories
- `make pipeline-overnight SUPER=components` - Long-running unattended scrape

## Getting Started

### Prerequisites
- Python 3.10+
- OpenAI API key (for AI-powered recommendations)
- Make (optional, for convenience commands)

### Quick Start

1. **Clone & install**
   ```bash
   git clone https://github.com/tim06927/Daiy.git
   cd Daiy
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   make install  # or: pip install -r requirements.txt
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

3. **Start the web app**
   ```bash
   make run
   # or: python web/app.py
   # Visit http://127.0.0.1:5000
   ```

## Running the Web App

The main interface for user interaction:

```bash
python web/app.py
```

Then visit `http://127.0.0.1:5000` in your browser and:
1. Describe your bike upgrade project in plain text
2. Upload an optional bike photo (for visual analysis)
3. Answer any clarification questions the AI generates
4. Review AI recommendations with per-product explanations
5. Click product links to visit bike-components.de

**Features:**
- Natural language input with optional image upload
- Smart clarification - AI asks targeted questions about unclear specs
- Grounded recommendations - Only real products from inventory
- Per-product explanations - Why each product fits your needs
- Direct links to product pages

## Scraping Fresh Data

The scraper fetches product data from bike-components.de and stores it in SQLite:

### Quick scrape (incremental - skip existing products)
```bash
python -m scrape.cli
```

### Full refresh (rescrape everything)
```bash
python -m scrape.cli --mode full --max-pages 10
```

### Overnight mode (extra-slow delays for unattended runs)
```bash
python -m scrape.cli --overnight --max-pages 100
```

### Discover and scrape a category tree
```bash
# Discover all subcategories under components/drivetrain
python -m scrape.cli --discover-scrape components/drivetrain --dry-run

# Scrape all discovered subcategories
python -m scrape.cli --discover-scrape components/drivetrain --max-pages 2
```

### Discover fields for a category
```bash
python -m scrape.discover_fields cassettes --sample-size 20
```

**Scraper features:**
- Polite scraping with random delays
- Exponential backoff on server errors (429, 5xx)
- Graceful Ctrl+C shutdown (auto-saves progress)
- Pagination support (follows all pages in a category)
- Automatic field discovery and storage
- SQLite storage with type-safe dynamic specs
- CSV export for easy viewing
- Comprehensive JSONL logging

## Data Storage

Product data is stored in a **shared SQLite database** used by both scraper and web app:

### SQLite Database (Primary - Recommended)
Located at `data/products.db` with schema:

```
products (core product info + 1500+ dynamic spec columns)
├── id, category, name, url, brand, price
├── image_url, sku, breadcrumbs, description
├── specs (JSON with product specifications)
├── created_at, updated_at
└── [1500+ category-specific columns for filtering]

Indexes:
├── idx_category ON products(category)  -- Fast category queries
└── idx_name ON products(name)          -- Fast name searches
```

**Benefits:**
- **Memory efficient**: Queries only needed products (0.2-5MB per query)
- **Fast**: Indexed queries return results in <100ms
- **Shared**: Scraper writes, web app reads (no sync needed)
- **Real-time**: New products available immediately
- **Deployable**: Fits in 512MB RAM environments (Render free tier)

**Database Stats:**
- File size: 45.6 MB
- Products: 11,000+
- Categories: 200+
- Memory usage: <50MB (vs 500MB+ for CSV)

### Pipeline Flow

```
Scraper writes → products.db ← Web app queries
      ↓              ↓              ↓
  New products   SQLite file   On-demand loading
  Categories     Indexed       Real-time updates
```

See [PIPELINE.md](PIPELINE.md) for details on scraper → web app integration.

### CSV Export (Optional)
Located at `data/products.db` with schema:

```
products (core product info)
├── id, category, name, url, brand, price
├── image_url, sku, breadcrumbs, description
├── specs_json (raw scraped specs)
└── created_at, updated_at

dynamic_specs (flexible spec storage)
├── product_id, category, field_name, field_value
└── Stores normalized specs for any category

discovered_fields (field discovery results)
├── category, field_name, original_labels
├── frequency, sample_values
└── discovered_at
```

### CSV Export
Export database to CSV with flattened fields:
```bash
python -m scrape.csv_utils --export data/bc_products.csv
```

## Architecture Decisions

- **Modular frontend** - Separate CSS/JS files for maintainability (153-line HTML template)
- **Type-safe dynamic specs** - Flexible product field storage using `Mapping[str, Optional[str]]`
- **SQLite database** - Normalized schema with dynamic spec tables
- **CSV export** - For easy viewing and sharing
- **Category spec registry** - Flexible field mapping per product category in [scrape/config.py](scrape/config.py)
- **Grounding pattern** - LLM can only recommend real products from inventory
- **Smart clarification** - AI infers missing specs before asking user (confidence-based)
- **Per-product explanations** - Each recommendation includes "why it fits"
- **Comprehensive logging** - JSONL logs for all interactions with HTML viewer

## Environment Variables

See [.env.example](.env.example) for all available options:

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | Your OpenAI API key |
| `FLASK_HOST` | No | Host to bind (default: 0.0.0.0) |
| `FLASK_PORT` | No | Port (default: 5000) |
| `FLASK_DEBUG` | No | Debug mode (default: False) |
| `DEMO_USER` | No | Basic auth username |
| `DEMO_PASS` | No | Basic auth password |
| `MAX_CASSETTES` | No | Product limit (default: 5) |
| `MAX_CHAINS` | No | Product limit (default: 5) |
| `MAX_TOOLS` | No | Product limit (default: 5) |

## Documentation

- **[Web App README](web/README.md)** - Three-phase flow, API endpoints, UI details
- **[Web FLOW.md](web/FLOW.md)** - Sequence diagrams and decision trees
- **[Frontend Architecture](web/static/README.md)** - Modular CSS/JS structure
- **[Scraper README](scrape/README.md)** - Scraping workflows, configuration, field discovery
- **[Web Tests README](web/tests/README.md)** - Test fixture documentation

## Testing

Both web and scraper modules include comprehensive test suites:

```bash
# Run all tests
python -m pytest web/tests/ scrape/tests/ -v

# Run specific test
python -m pytest web/tests/test_model_clarification.py -v

# Run with coverage
python -m pytest --cov=web --cov=scrape
```

**Test coverage includes:**
- LLM prompt generation and response parsing
- Dynamic clarification questions
- Product candidate selection
- Vision/image processing
- Dynamic specs type safety
- Pagination extraction
- Field discovery algorithms

## Contributing

This project uses:
- **GitHub Copilot** for development assistance
- **pytest** for testing
- **SQLite** for data storage
- **Flask** for web framework
- **OpenAI API** for LLM capabilities

## License

[MIT License](LICENSE) (or specify your license)

## Future Enhancements

- [ ] Multi-language support
- [ ] Price history and trend tracking
- [ ] User preference persistence
- [ ] Performance metrics (weight, durability, compatibility)
- [ ] Community reviews integration
- [ ] Automatic schema generation from discovered fields
- [ ] Multi-threaded/async scraping
- [ ] GraphQL API for product data
- [ ] Mobile app version
