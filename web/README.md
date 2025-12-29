# Daiy Web App

A Flask-based web interface for AI-powered bike component recommendations with a modern split-panel UI.

## Overview

The web app provides a user-friendly interface to:
1. Describe a bike upgrade project (text + optional image)
2. Get smart clarification if speed/use-case is unclear
3. View AI recommendations grounded in real product data
4. Browse products with per-item explanations
5. Access installation instructions and checklists

The app uses a grounding pattern: all recommendations come from a real product catalog, preventing the LLM from hallucinating products.

## Features

- **Natural language input** - Describe your project in plain text
- **Image upload** - Optional bike photo for visual analysis
- **Smart clarification** - AI infers missing info or asks targeted questions with helpful hints
- **Split-panel UI** - Query context on left, results on right
- **Per-product explanations** - Each product shows "why it fits" your needs
- **Tabbed results** - Products and installation instructions in separate tabs
- **Grounded recommendations** - Only suggests real products in inventory
- **Direct links** - One-click access to bike-components.de product pages
- **Optional basic auth** - Protect demos with username/password

## Project Structure

```
web/
├── app.py              # Flask app setup and routes
├── api.py              # API endpoints (/api/recommend, /api/categories)
├── categories.py       # Product category definitions
├── candidate_selection.py  # Product filtering logic
├── catalog.py          # Product catalog loading
├── config.py           # Centralized configuration
├── image_utils.py      # Image processing for OpenAI
├── job_identification.py  # LLM-based job/category identification
├── logging_utils.py    # Interaction logging
├── prompts.py          # Prompt building for LLM calls
├── templates/
│   └── index.html      # Single-page app (CSS/JS inline)
├── logs/               # LLM interaction logs (JSONL)
├── tests/              # Test files
│   ├── test_model_clarification.py
│   ├── test_model_clarification_extended.py
│   └── test_vision_flow.py
└── README.md           # This file
```

## Files

### `app.py`
Slim Flask application (~100 lines) with:
- **Basic auth** - Optional HTTP Basic Auth for demos
- **Flask setup** - App initialization and blueprint registration
- **Index route** - GET `/` serves the main page

### `api.py`
API endpoints module with:
- **Job identification** - LLM determines product categories from user input
- **Smart clarification** - LLM infers missing values before asking user
- **Candidate selection** - Filters products by category and fit dimensions
- **Recommendation** - LLM generates grounded product recommendations
- **POST `/api/recommend`** - Main recommendation endpoint
- **GET `/api/categories`** - List available product categories

### `categories.py`
Product category definitions:
- `PRODUCT_CATEGORIES` - Category configs with fit dimensions
- `SHARED_FIT_DIMENSIONS` - Common dimensions (gearing, use_case, etc.)
- Helper functions for clarification fields

### `config.py`
Centralized settings:
- `CSV_PATH` - Absolute path to product data
- `LLM_MODEL` - Model to use (gpt-5-mini)
- `FLASK_HOST/PORT/DEBUG` - Server settings (env overridable)
- `MAX_CASSETTES/CHAINS/TOOLS` - Candidate limits per category

### `templates/index.html`
Single-page app (~1700 lines) with inline CSS and JavaScript:
- **Two-state UI** - Initial search state and results state
- **Tab selector** - Search (disabled) and AI modes
- **Split-panel results** - Left panel (query context), right panel (products)
- **Clarification UI** - Speed/use-case selection with helpful hints
- **Results tabs** - Products and Instructions views
- **Responsive design** - Works on desktop and mobile

## Setup

### Prerequisites
- Python 3.8+
- OpenAI API key with access to `gpt-5-mini`
- Product data CSV at `data/bc_products_sample.csv`

### Installation

```bash
# From project root
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Run the app
python web/app.py
```

The app will start at `http://127.0.0.1:5000`

## Usage

### Web Interface

1. Open http://127.0.0.1:5000
2. Describe your upgrade project (e.g., "I have a 12-speed gravel bike and need a new cassette")
3. (Optional) Upload an image of your bike/drivetrain
4. Click the search button (→)
5. If needed, select speed or use-case from clarification options
6. View recommendations with product cards and installation instructions

### API Endpoint

POST `/api/recommend`:

**Request:**
```json
{
  "problem_text": "I want to upgrade my 11-speed road bike cassette for better climbing",
  "image_base64": "...",
  "selected_values": {"gearing": 11, "use_case": "road"},
  "cached_job": null
}
```

**Response (needs clarification):**
```json
{
  "need_clarification": true,
  "job": {
    "categories": ["drivetrain_cassettes"],
    "inferred_values": {}
  },
  "missing_dimensions": ["gearing"],
  "options": {
    "gearing_options": [10, 11, 12]
  },
  "hints": {
    "gearing": "Count the cogs on your rear cassette..."
  },
  "inferred_values": {}
}
```

**Response (success):**
```json
{
  "diagnosis": "You want better climbing range on your 11-speed road bike",
  "sections": {
    "why_it_fits": ["Matches 11-speed drivetrain", "Wider range for climbing"],
    "suggested_workflow": ["Remove old cassette", "Install new cassette"],
    "checklist": ["Cassette lockring tool", "Chain breaker"]
  },
  "products_by_category": [
    {
      "category": "Cassettes",
      "category_key": "drivetrain_cassettes",
      "best": {
        "name": "Shimano CS-HG700-11",
        "price": "44.99€",
        "url": "https://bike-components.de/...",
        "why_it_fits": "11-34 range provides excellent climbing"
      },
      "alternatives": []
    }
  ],
  "job": {"categories": ["drivetrain_cassettes"]},
  "fit_values": {"gearing": 11, "use_case": "road"}
}
```

## Configuration

Environment variables (see `.env.example` in project root):

```bash
OPENAI_API_KEY=sk-...        # Required
FLASK_HOST=0.0.0.0           # Optional (default: 0.0.0.0)
FLASK_PORT=5000              # Optional (default: 5000)
FLASK_DEBUG=True             # Optional (default: False)
DEMO_USER=demo               # Optional basic auth
DEMO_PASS=changeme           # Optional basic auth
MAX_CASSETTES=5              # Optional (default: 5)
MAX_CHAINS=5                 # Optional (default: 5)
MAX_TOOLS=5                  # Optional (default: 5)
```

## How It Works

### Data Flow

1. **Load Catalog** - App loads CSV on startup, derives speed from product names
2. **User Input** - User describes their project (text + optional image)
3. **Regex Inference** - Extract speed/use-case from text patterns
4. **LLM Inference** - If regex fails, ask LLM to infer or propose options
5. **Clarification** - If still unclear, show options with helpful hints
6. **Select Candidates** - Filter products by speed and use case
7. **Build Context** - Create JSON with filtered products for LLM
8. **Generate Recommendation** - LLM picks best products with explanations
9. **Display Results** - Show product cards + installation instructions

### Grounding Pattern

The prompt includes:
- User's problem description
- Detected bike specs (speed, use case)
- **Candidate products only** (real inventory)
- Explicit instruction: "recommend from the provided candidates only"
- Structured JSON output format

This ensures:
- No hallucinated products
- All URLs are real and verifiable
- Recommendations respect technical constraints
- Per-product explanations for transparency

## Logging

All LLM interactions are logged to `web/logs/llm_interactions_YYYYMMDD.jsonl`:
- User inputs and image metadata
- Regex inference results
- LLM prompts and responses
- Clarification requests

Use `python web/view_logs.py` to inspect logs.

## Troubleshooting

### "No products found"
- Verify `data/bc_products_sample.csv` exists
- Run scraper: `python scrape/cli.py`
- Check that products have speed info in their names

### "OpenAI API error"
- Check `OPENAI_API_KEY` in `.env` file
- Verify API key has access to gpt-5-mini
- Check API quota and usage limits

### "need_clarification keeps appearing"
- Be more specific: "12-speed gravel bike" instead of "my bike"
- Or select from the provided options

## Performance Tips

- **Catalog caching** - Loaded once at startup
- **Candidate limits** - MAX_CASSETTES/CHAINS/TOOLS reduce context size
- **Early filtering** - `select_candidates()` filters before LLM call
- **Single LLM call** - Recommendation uses one API call
