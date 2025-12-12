# Daiy Web App

A Flask-based web interface for getting grounded AI recommendations for bike component upgrades.

## Overview

The web app provides a user-friendly interface to:
1. Describe a bike upgrade project
2. Get AI-powered recommendations grounded in real product data
3. View candidate products with pricing and specs
4. Access direct links to bike-components.de

The app uses the same grounding pattern as the demo: all recommendations come from a real product catalog, preventing the LLM from hallucinating products.

## Features

- **Problem-based input** - Users describe what they're trying to achieve
- **Grounded recommendations** - LLM only suggests real products in stock
- **Product tiles** - Browse cassettes and chains with prices and brands
- **Reasoning** - Detailed explanation of why products were chosen
- **Direct links** - One-click access to product pages on bike-components.de

## Project Structure

```
web/
├── app.py              # Main Flask application
├── config.py           # Centralized configuration
├── templates/          # HTML templates
│   ├── base.html      # Base template with CSS
│   └── index.html     # Main page
└── README.md          # This file
```

## Files

### `app.py`
Main application with:
- **Product loading** - Reads CSV catalog at startup
- **Candidate selection** - Filters products by speed and use case
- **Context building** - Prepares grounding data for LLM
- **LLM integration** - Calls gpt-5-nano with structured prompt
- **Flask routes** - Handles GET/POST requests
- **JSON API** - `/api/recommend` endpoint for frontend

Key functions:
- `load_catalog()` - Parse CSV, derive speed/application
- `select_candidates()` - Filter cassettes/chains
- `build_grounding_context()` - Create LLM context
- `make_prompt()` - Format prompt with instructions
- `call_llm()` - Call OpenAI API
- `extract_json_summary()` - Parse machine-readable JSON from LLM response
- `remove_json_summary()` - Strip JSON from user-facing text

### `config.py`
Centralized settings:
- `CSV_PATH` - Path to product data
- `LLM_MODEL` - Model to use (gpt-5-nano)
- `FLASK_HOST/PORT/DEBUG` - Server settings
- `DEFAULT_BIKE_SPEED` - Default drivetrain speed
- `DEFAULT_USE_CASE` - Default filter (Road/MTB/Gravel)
- `MAX_CASSETTES/CHAINS` - Candidate limits

### `templates/`
HTML templates:
- `base.html` - CSS styling and layout
- `index.html` - Main page with form and results

## Setup

### Prerequisites
- Python 3.8+
- OpenAI API key with access to `gpt-5-nano`
- Product data CSV at `data/bc_products_sample.csv`

### Installation

```bash
# Set API key
export OPENAI_API_KEY="sk-..."

# Run the app
python web/app.py
```

The app will start at `http://127.0.0.1:5000`

## Usage

### Web Interface

1. Open http://127.0.0.1:5000
2. Describe your upgrade project (e.g., "I have a 11-speed road bike and want to upgrade my cassette for better climbing")
3. (Optional) Upload an image of your bike
4. Click "Get Recommendation"
5. View the LLM's analysis and product candidates

### API Endpoint

POST `/api/recommend`:
```json
{
  "problem_text": "I want to upgrade my cassette for better climbing"
}
```

Response:
```json
{
  "answer": "Recommended combination:\n- Cassette: ...\n- Chain: ...\n\nWhy these fit...",
  "products": [
    {
      "type": "cassette",
      "name": "Shimano CS-HG700-11 11-speed Cassette",
      "brand": "Shimano",
      "price": "44.99€",
      "url": "https://bike-components.de/..."
    },
    ...
  ],
  "summary": {
    "cassette_url": "https://bike-components.de/...",
    "chain_url": "https://bike-components.de/...",
    "notes": ["Both 11-speed compatible", "Wider range for climbing", ...]
  }
}
```

**Note:** The `answer` field contains only the human-readable explanation. The machine-readable JSON summary is extracted and returned separately in the `summary` field, but not displayed to the user in the main answer text.

## Configuration

Edit `config.py` to customize:

```python
# Change LLM model
LLM_MODEL = "gpt-4"

# Different default bike speed (12-speed)
DEFAULT_BIKE_SPEED = 12

# More candidates shown
MAX_CASSETTES = 10
MAX_CHAINS = 10

# Server settings
FLASK_PORT = 8000
FLASK_DEBUG = False
```

## How It Works

### Data Flow

1. **Load Catalog** - App loads CSV on startup
2. **Parse Products** - Derive speed, application, specs
3. **User Input** - User describes their project
4. **Select Candidates** - Filter by bike speed and use case
5. **Build Context** - Create JSON for LLM with candidates
6. **Call LLM** - gpt-5-nano reads context and problem
7. **Generate Response** - LLM explains choice with reasoning
8. **Display Results** - Show explanation + product tiles

### Grounding Pattern

The prompt includes:
- User's problem description
- Bike specs (speed, use case, constraints)
- **Candidate products only** (real inventory)
- Explicit instruction: "ONLY recommend from this list"
- Structured output format (JSON)

This ensures:
- No hallucinated products
- All URLs are real and verifiable
- Recommendations respect technical constraints
- Responses are machine-readable

## LLM Response Handling

The app handles responses with reasoning blocks and extracts structured data:

```python
# 1. Call LLM
for item in resp.output:
    if hasattr(item, "content") and item.content is not None:
        return item.content[0].text
```

This works with gpt-5-nano's extended thinking capability.

```python
# 2. Extract machine-readable JSON
json_summary = extract_json_summary(answer_text)
# Example: {"cassette_url": "...", "chain_url": "...", "notes": [...]}

# 3. Remove JSON from user-facing text
answer_text_clean = remove_json_summary(answer_text)
# Clean text without the JSON block at the end
```

The LLM generates both:
- **Human-readable explanation** - Shown to the user
- **Machine-readable JSON** - Parsed and returned separately in the API response

This separation ensures users see clean, natural language recommendations while the frontend can still access structured data for highlighting specific products or other UI features.

## Extending the App

### Add More Categories

Update `config.py`:
```python
CANDIDATE_CATEGORIES = ["cassettes", "chains", "brakes"]
```

Update `select_candidates()` to handle each category.

### Customize Bike Profiles

Instead of hardcoded 11-speed road, load from user input:
```python
bike_speed = int(request.json.get("bike_speed", DEFAULT_BIKE_SPEED))
use_case = request.json.get("use_case", DEFAULT_USE_CASE)
```

### Add Image Upload Processing

The form accepts image uploads but currently ignores them. To use them:

```python
@app.route("/api/recommend", methods=["POST"])
def api_recommend():
    data = request.form
    file = request.files.get("image")
    
    if file:
        # Use vision API to analyze bike image
        # Extract frame material, gearing, condition, etc.
        pass
```

### Database Integration

Instead of CSV, load products from PostgreSQL:
```python
import psycopg2
conn = psycopg2.connect("dbname=daiy user=tim")
CATALOG_DF = pd.read_sql("SELECT * FROM products", conn)
```

## Troubleshooting

### "No products found"
- Verify `data/bc_products_sample.csv` exists
- Run scraper: `python scrape/cli.py`
- Check DEFAULT_BIKE_SPEED and DEFAULT_USE_CASE match your data

### "OpenAI API error"
- Set `OPENAI_API_KEY` environment variable
- Verify API key has gpt-5-nano access
- Check API quota and usage

### "CSV parsing failed"
- Ensure CSV has required columns: category, name, url, speed, application, specs
- Check for encoding issues: use UTF-8
- Verify JSON specs column is properly escaped

### LLM returns empty response
- Check if response has content (sometimes all reasoning, no output)
- Increase token limit in config
- Simplify prompt or problem text

## Performance Tips

- **Caching** - Load catalog once at startup (already done)
- **Candidate limits** - Use MAX_CASSETTES/CHAINS to reduce context
- **Filter early** - select_candidates() filters before formatting
- **Async** - Consider using async Flask for concurrent requests

## Future Ideas

- [ ] make sure input is striped of PII and add a super simple consent layer
- [ ] Multi-turn conversation (refine recommendations)
- [ ] User authentication and saved recommendations
- [ ] Image analysis of user's bike
- [ ] Compatibility checking between components
- [ ] Price comparison across retailers
- [ ] Installation difficulty rating
- [ ] Community reviews and ratings
- [ ] Performance metrics comparison (weight, efficiency, durability)
