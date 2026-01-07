# Daiy

## Current Status (Dec 30, 2025)

**Major Prompt Rework & Frontend Restructuring - Production-Ready Architecture**

Just completed significant improvements to both backend and frontend:

### Backend: LLM Prompt Flow (Previously completed)
1. **Job Identification** - Generates step-by-step instructions with `[category_key]` placeholders
2. **Clarification** - Simplified to only ask LLM-identified unclear specs (no hardcoded lists)
3. **Recommendation** - Replaces placeholders with actual products and provides reasoning

### Frontend: Modular Architecture (NEW - Just Completed)
Restructured monolithic 2200-line `index.html` into maintainable modules:

**Before:** Single `index.html` (2199 lines - CSS + JS + HTML)  
**After:** Clean separation into 10 focused files:
- **3 CSS modules** (base, components, products) - 1190 lines
- **7 JavaScript modules** (config, state, image, api, clarification, products, main) - 1107 lines  
- **Clean HTML template** - 153 lines (93% reduction)

**Benefits:**
- ✅ **Maintainable** - Each module has a single responsibility
- ✅ **Collaborative** - Multiple developers can work in parallel
- ✅ **Debuggable** - Browser DevTools shows precise file/line numbers
- ✅ **Performant** - Better caching, non-blocking CSS, optimized load order
- ✅ **Documented** - Comprehensive architecture guide in `/web/static/README.md`

See [RESTRUCTURING_SUMMARY.md](RESTRUCTURING_SUMMARY.md) for full details of the frontend refactoring.

### Key Improvements (Full Stack)
- ✅ All clarification questions are **dynamic** and **LLM-generated**
- ✅ **Multi-category support** - Products can belong to multiple categories (no duplicates or missing items)
- ✅ **Comprehensive logging** - User inputs, clarifications, LLM calls/responses
- ✅ **HTML log viewer** - Sessions organized with filters and collapsible sections
- ✅ **Modular frontend** - Separate CSS/JS files for easy maintenance
- ✅ **Clear architecture** - Three-phase LLM flow with proper separation of concerns
- ✅ **Better documentation** - FLOW.md, static/README.md, architecture diagrams

### For Developers
- Backend flow: [web/README.md](web/README.md) and [web/FLOW.md](web/FLOW.md)
- Frontend architecture: [web/static/README.md](web/static/README.md)
- Multi-category support: [docs/MULTI_CATEGORY_SUPPORT.md](docs/MULTI_CATEGORY_SUPPORT.md)
- Restructuring details: [RESTRUCTURING_SUMMARY.md](RESTRUCTURING_SUMMARY.md)

---

## About Daiy

A startup that aims to help every DIYer find the right parts and tools using multimodal AI.

## Vibe Coding and PoC Disclaimer

Large parts of this project are vibe-coded using GitHub Copilot, ChatGPT, and more. Further, this is a proof of concept and not a production-ready project. Parts of this repo (CODING_STANDARDS, somewhat excessive documentation, ...) exist to make the AI do a good job and not to put an overbearing burden on humans. Proceed with fun and care when using.

## Daiy PoC Architecture

This repository demonstrates a **three-phase LLM-powered recommendation system** with grounded product suggestions:

1. **Job Identification** (`identify_job`) - LLM analyzes user input and generates step-by-step instructions
2. **Smart Clarification** (optional) - If specs are unclear (confidence < 0.8), ask user targeted questions
3. **Grounded Recommendation** - LLM selects from real catalog and provides per-product reasoning

**Key principle:** All recommendations use actual products from inventory; no hallucinations.

The system is:
- **Multimodal** - Accepts text queries and optional bike photos
- **Generalized** - Job identification prompts are neutral to repair type (not hardcoded to bikes)
- **Observable** - Comprehensive JSONL logging of all LLM interactions
- **Maintainable** - Clear separation of concerns with focused modules

### Three Main Components

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
│   ├── __init__.py     # Package init with convenient exports
│   ├── logs/           # Scraper operation logs (JSONL)
│   ├── config.py       # Configuration, URLs, delays, retry settings
│   ├── models.py       # Data models (Product dataclass)
│   ├── scraper.py      # Scraping logic with pagination and retries
│   ├── db.py           # SQLite database schema and helpers
│   ├── html_utils.py   # HTML parsing
│   ├── csv_utils.py    # CSV export/import
│   ├── workflows.py    # High-level scraping workflows
│   ├── cli.py          # Command-line interface
│   ├── discover_fields.py    # Auto-discover spec fields
│   ├── discover_categories.py # Auto-discover categories
│   ├── view_data.py          # HTML data viewer for scrape status
│   ├── logging_config.py     # Structured JSONL logging
│   ├── shutdown.py           # Graceful shutdown handling
│   ├── url_validation.py     # URL security validation
│   └── README.md       # Scraper documentation
├── grounded_demo/      # AI recommendation demo (CLI)
│   ├── demo.py         # Main demo script
│   ├── catalog.py      # Product context building
│   └── README.md       # Demo documentation
├── data/               # Product data
│   ├── bc_products_sample.csv  # Scraped bike components (CSV)
│   ├── products.db             # SQLite database (primary storage)
│   ├── discovered_categories.json  # Category hierarchy from sitemap
│   └── scrape_data_view.html   # Generated data viewer report
├── .env.example        # Environment template (copy to .env)
├── requirements.txt    # Python dependencies
└── README.md           # This file
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

### Grounded AI Demo (`grounded_demo/`)

CLI-based LLM recommendations grounded in real product data:
- **Grounding pattern** - Only suggests products from catalog
- **Reasoning** - Explains why products fit the user's needs
- **Structured output** - JSON summary for downstream use

```bash
python grounded_demo/demo.py
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
- `make refresh-data` - One command to update product data and prepare for commit
- `make pipeline SUPER=components/drivetrain` - Discover and scrape all subcategories
- `make pipeline-overnight SUPER=components` - Long-running unattended scrape

## Setup

### Prerequisites
- Python 3.8+
- OpenAI API key (for AI features)
- Make (optional, for convenience commands)

### Quick Start

1. **Clone & install**
   ```bash
   git clone <repo>
   cd Daiy
   python -m venv .venv
   source .venv/bin/activate
   make install  # or: pip install -r requirements.txt
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ```

3. **Run the web app**
   ```bash
   python web/app.py
   # Visit http://127.0.0.1:5000
   ```

4. **(Optional) Scrape fresh data**
   ```bash
   python scrape/cli.py
   ```

## Sample Data and Database

Product data is sourced from bike-components.de via the scraper. Data includes:
- Product name, brand, price
- Product image URLs
- Technical specifications (category-specific normalized fields)
- Product URLs
- Category classification

**Storage approach:**
- **SQLite database** (primary) - Normalized schema at `data/products.db`
- **CSV export** - For easy viewing and sharing
- The web app can load from either CSV or database

**Database schema:**
- `products` - Core product info (name, URL, image, price, etc.)
- `chain_specs` - Chain-specific fields (gearing, links, closure type)
- `cassette_specs` - Cassette-specific fields (gradation, material)
- `glove_specs`, `tool_specs` - Other category tables
- `scrape_state` - Pagination tracking for resumable scrapes

## Workflow

1. **Scrape** - Run scraper to fetch fresh product data
2. **Store** - Products are saved to CSV
3. **Describe** - User describes their bike upgrade project
4. **Infer** - AI infers speed/use-case or asks clarifying questions
5. **Filter** - Select candidate products matching constraints
6. **Recommend** - LLM picks best products with explanations
7. **Output** - Product cards with install instructions

## Example: Cassette Upgrade

Input:
> "I have an 11-speed road bike and want better climbing range"

AI Response:
- **Diagnosis**: "You want to improve climbing on your 11-speed road bike"
- **Best cassette**: Shimano CS-HG700-11 11-34T (wider range)
- **Best chain**: KMC X11 (durable, compatible)
- **Tools needed**: Cassette lockring tool, chain breaker
- **Why it fits**: Matches your 11-speed drivetrain, 11-34 provides wider climbing range

## Documentation

- **[Web App README](web/README.md)** - Flask app setup, API, and UI details
- **[Scraper README](scrape/README.md)** - Scraping configuration and usage
- **[Grounded Demo README](grounded_demo/README.md)** - CLI demo customization

## Architecture Decisions

- **Single-file frontend** - All CSS/JS inline in index.html for deployment simplicity
- **SQLite database** - Normalized schema with category-specific spec tables
- **CSV export** - For easy viewing, sharing, and backward compatibility
- **Category spec registry** - Flexible field mapping per product category
- **Grounding pattern** - LLM can only recommend real products from inventory
- **Smart clarification** - AI infers missing info before asking user
- **Per-product explanations** - Each recommendation includes "why it fits"
- **gpt-5-mini** - Cost-effective model for recommendations

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

## Future Roadmap

- [ ] Multi-language support
- [ ] Price history and trend tracking
- [ ] User preference learning
- [ ] Performance metrics (weight, durability)
- [ ] Compatibility checking between components
- [ ] Community reviews integration
- [ ] Automatic schema generation from discovered fields
- [ ] Multi-threaded/async scraping