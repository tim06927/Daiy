# Daiy

## About Daiy

An startup that aims to help every DIYler to find the right parts and tools using multimodal AI.

## Daiy PoC

This repository contains a proof of concept (PoC) for Daiy that demonstrates:
- **Web scraping** - Automated extraction of real bike component data
- **Grounded AI** - LLM recommendations using only real products from inventory
- **Product database** - Structured storage and retrieval of bike parts
- **AI integration** - API-driven recommendations with reasoning

## Project Structure

```
├── scrape/              # Web scraper for bike-components.de
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
├── daiy_web/           # Flask web app for recommendations
│   ├── app.py          # Flask application
│   ├── config.py       # Configuration
│   ├── templates/      # HTML templates
│   └── README.md       # Web app documentation
├── data/               # Product data
│   ├── bc_products_sample.csv  # Scraped bike components
│   └── sampleData/     # Additional sample data (archived)
├── scripts/            # Database & setup scripts (archived)
└── README.md          # This file
```

## Key Features

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

LLM-powered recommendations grounded in real product data:
- **Grounding pattern** - Only suggests products from catalog
- **Reasoning** - Explains why products fit the user's needs
- **Structured output** - JSON summary for downstream use
- **Real data** - Uses products from the scraper

```bash
python grounded_demo/demo.py
```

### Web App (`daiy_web/`)

Flask web interface for AI recommendations:
- **User-friendly form** - Describe your upgrade project
- **Grounded results** - Real products from inventory
- **Product tiles** - Browse candidates with pricing
- **Direct links** - One-click to bike-components.de

```bash
# Make sure you have product data first
python scrape/cli.py

# Then run the web app
python daiy_web/app.py
# Visit http://127.0.0.1:5000
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

2. **Scrape bike components**
   ```bash
   python scrape/cli.py
   ```

3. **Run the AI demo**
   ```bash
   export OPENAI_API_KEY="sk-..."
   python grounded_demo/demo.py
   ```

4. **Or run the web app**
   ```bash
   python daiy_web/app.py
   # Visit http://127.0.0.1:5000
   ```

## Sample Data and Database

Product data is sourced from bike-components.de via the scraper. Data includes:
- Product name, brand, price
- Technical specifications
- Product URLs
- Category classification

**Current approach:** CSV-first, lightweight, and easy to use.
- Scraped products are saved to `data/bc_products_sample.csv`
- The web app and demo load directly from CSV

**Archived for later:** Database setup (99spokes dataset, PostgreSQL schemas) have been archived. These can be restored when needed for persistent storage or advanced queries.

## Workflow

1. **Scrape** - Run scraper to fetch fresh product data
2. **Store** - Products are saved to CSV (can import to DB)
3. **Query** - Load products for AI recommendations
4. **Recommend** - Use LLM to suggest compatible products
5. **Output** - Structured JSON with URLs and reasoning

## Example: Cassette Upgrade

Input:
- User has 11-speed road bike
- Current: 11-32 cassette
- Goal: Wider range for climbing

Output from grounded demo:
```json
{
  "cassette_url": "https://bike-components.de/...",
  "chain_url": "https://bike-components.de/...",
  "notes": [
    "Both 11-speed, compatible with your drivetrain",
    "11-34 cassette provides wider climbing range",
    "Proven Shimano pairing for reliability"
  ]
}
```

## Documentation

- **[Scraper README](scrape/README.md)** - Detailed scraping configuration, usage, and extension
- **[Grounded Demo README](grounded_demo/README.md)** - AI recommendation pattern and customization
- **[Web App README](daiy_web/README.md)** - Flask app setup, API, and customization

## Architecture Decisions

- **Modular scraper** - Easy to extend for new sites/categories
- **CSV-first** - Simple export, flexible import options
- **Grounding pattern** - Reliable AI recommendations without hallucination
- **Incremental scraping** - Efficient updates, avoids re-scraping
- **gpt-5-nano** - Cost-effective reasoning model for recommendations

## Future Roadmap

- [ ] Database integration (PostgreSQL/SQLite)
- [ ] REST API for recommendations
- [ ] Web interface for browsing products
- [ ] Multi-language support
- [ ] Pagination support for large categories
- [ ] Price history and trend tracking
- [ ] User preference learning
- [ ] Performance metrics (weight, durability, cost-per-tooth)