# Quick Start Guide

Get Daiy running in 5 minutes.

## Installation

### 1. Clone & Navigate
```bash
git clone https://github.com/tim06927/daiy.git
cd daiy
```

### 2. Create Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Set API Key
```bash
export OPENAI_API_KEY="your-api-key-here"
```

## Run the Web App

```bash
cd daiy_web
python app.py
```

Open http://127.0.0.1:5000 in your browser.

Type a problem: *"I ride road bikes and want a cassette with a wider range for climbing"*

Get a grounded recommendation with real product URLs.

## Run the CLI Demo

```bash
cd grounded_demo
python demo.py
```

See the full prompt sent to the LLM and the recommendation response.

## Scrape New Data

```bash
python scrape/cli.py --mode incremental
```

This adds new products from bike-components.de to `data/bc_products_sample.csv`.

## Project Structure

- **scrape/** - Web scraper for bike components
- **grounded_demo/** - CLI proof-of-concept
- **daiy_web/** - Flask web application
- **data/** - CSV data files
- **ARCHITECTURE.md** - Deep dive into design patterns
- **CONTRIBUTING.md** - Guidelines for developers

## Key Concept: Grounding

The LLM can **only recommend products in the CSV**.

This prevents hallucination and ensures all recommendations are:
- Real (products actually exist)
- Available (in stock)
- Actionable (users can click the URL)

## Next Steps

- Check `CONTRIBUTING.md` for coding standards
- Explore each module's README for detailed docs
- Modify prompts/filters in code to customize behavior

## Support

See README.md for full project overview and support information.

---

Happy recommending! 🚴
