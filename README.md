# Daiy

## About Daiy

A startup that aims to help every DIYer find the right parts and tools using multimodal AI.

## Vibe Coding and PoC Disclaimer

Large parts of this project are vibe-coded using GitHub Copilot, ChatGPT, and more. Further, this is a proof of concept and not a production-ready project. Parts of this repo (CODING_STANDARDS, somewhat excessive documentation, ...) exist to make the AI do a good job and not to put an overbearing burden on humans. Proceed with fun and care when using.

## Daiy PoC

This repository contains a proof of concept (PoC) for Daiy that demonstrates:
- **Web scraping** - Automated extraction of real bike component data
- **Grounded AI** - LLM recommendations using only real products from inventory
- **Multimodal input** - Text descriptions and optional image uploads
- **Smart clarification** - AI infers missing info or asks targeted questions
- **Product database** - Structured storage and retrieval of bike parts

## Project Structure

```
├── web/                # Flask web app (main application)
│   ├── app.py          # Flask application with LLM integration
│   ├── config.py       # Centralized configuration
│   ├── templates/      # HTML templates (index.html)
│   ├── logs/           # LLM interaction logs (JSONL)
│   └── README.md       # Web app documentation
├── scrape/             # Web scraper for bike-components.de
│   ├── config.py       # Configuration & URLs
│   ├── models.py       # Data models
│   ├── scraper.py      # Scraping logic
│   ├── html_utils.py   # HTML parsing
│   ├── csv_utils.py    # CSV export/import
│   ├── cli.py          # Command-line interface
│   └── README.md       # Scraper documentation
├── grounded_demo/      # AI recommendation demo (CLI)
│   ├── demo.py         # Main demo script
│   ├── catalog.py      # Product context building
│   └── README.md       # Demo documentation
├── data/               # Product data
│   └── bc_products_sample.csv  # Scraped bike components
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

Modular scraper for bike-components.de:
- **Polite scraping** - Respects rate limits with random delays
- **Incremental mode** - Only scrapes new products (default)
- **Full refresh** - Option to rescrape everything
- **Category support** - Cassettes, chains, drivetrain tools, gloves
- **Rich data extraction** - Specs, SKU, pricing, descriptions

```bash
# Run incremental scrape (skip existing)
python scrape/cli.py

# Full refresh (ignore existing CSV)
python scrape/cli.py --mode full
```

### Grounded AI Demo (`grounded_demo/`)

CLI-based LLM recommendations grounded in real product data:
- **Grounding pattern** - Only suggests products from catalog
- **Reasoning** - Explains why products fit the user's needs
- **Structured output** - JSON summary for downstream use

```bash
python grounded_demo/demo.py
```

## Setup

### Prerequisites
- Python 3.8+
- OpenAI API key (for AI features)

### Quick Start

1. **Clone & install**
   ```bash
   git clone <repo>
   cd Daiy
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
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
- Technical specifications (speed derived from product names)
- Product URLs
- Category classification

**Current approach:** CSV-first, lightweight, and easy to use.
- Scraped products are saved to `data/bc_products_sample.csv`
- The web app loads directly from CSV at startup

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
- **CSV-first data** - Simple export, no database dependency
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

- [ ] Database integration (PostgreSQL/SQLite)
- [ ] Multi-language support
- [ ] Price history and trend tracking
- [ ] User preference learning
- [ ] Performance metrics (weight, durability)
- [ ] Compatibility checking between components
- [ ] Community reviews integration