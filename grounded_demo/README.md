# Grounded Demo

A demonstration of grounded AI recommendations using real product data from bike-components.de.

## Overview

This demo shows how to use an LLM with grounded context to make product recommendations. Instead of letting the model hallucinate products, we provide a curated list of real products and ask the model to choose from them.

The model receives:
- User context (bike specs, project goals, constraints)
- Real product candidates (cassettes and chains)
- A specific task (choose compatible parts and explain why)

The LLM responds with reasoned recommendations grounded in actual available products.

## Features

- **Grounded recommendations** - Only suggests products from the real catalog
- **Reasoning** - LLM explains why each product fits
- **Machine-readable output** - JSON summary for downstream use
- **Real data** - Uses products scraped from bike-components.de

## Project Structure

```
grounded_demo/
├── demo.py           # Main demo script
├── catalog.py        # Product loading and context building
└── README.md         # This file
```

## Files

### `demo.py`
Main entry point that:
1. Loads the product catalog
2. Builds grounding context
3. Creates a prompt with constraints
4. Calls the LLM (gpt-5-nano)
5. Displays the recommendation

Key functions:
- `make_prompt()` - Constructs prompt with context and task
- `call_llm()` - Calls OpenAI API with error handling
- `run_demo()` - Orchestrates the full flow

### `catalog.py`
Utilities for working with product data:
- `load_catalog()` - Reads CSV and returns DataFrame
- `build_grounding_context()` - Prepares product context for the LLM

## Setup

### Prerequisites
- Python 3.8+
- OpenAI API key with access to `gpt-5-nano` model
- Product data CSV (from `data/bc_products_sample.csv`)

### Installation

```bash
# Install dependencies
pip install openai pandas

# Set your API key
export OPENAI_API_KEY="sk-..."
```

## Usage

### Run the demo

```bash
python demo.py
```

This will:
1. Load available cassettes and chains from the product CSV
2. Create a scenario (user wants to upgrade to 11-speed road cassette)
3. Ask the LLM to recommend a matching pair
4. Display the recommendation with reasoning
5. Output a JSON summary

### Example Output

```
=== PROMPT ===
You are an experienced bike mechanic.
A user wants to upgrade their cassette.
Here is the project and the available products from ONE shop.
You MUST ONLY recommend products from the lists below.
...

=== RESPONSE ===
Recommended choice from the candidates

- Cassette: Shimano CS-HG700-11 11-speed Cassette
  - Gradation includes 11-34T, widening the range for climbs...
- Chain: Shimano Ultegra / XT / E-Bike CN-HG701-11 11-speed Chain
  ...

Machine-readable summary
{
  "cassette_url": "https://www.bike-components.de/en/Shimano/CS-HG700-11-11-speed-Cassette-p62072/",
  "chain_url": "https://www.bike-components.de/en/Shimano/Ultegra-XT-E-Bike-CN-HG701-11-11-speed-Chain-p44481/",
  "notes": [...]
}
```

## How It Works

### The Grounding Pattern

1. **Data Preparation** - Load real products from CSV
2. **Context Building** - Filter and format data for the LLM
3. **Constraint Injection** - Explicitly tell the LLM "ONLY recommend from this list"
4. **Task Definition** - Clear instructions on what to do
5. **Structured Output** - Request JSON for easy parsing

### Why Grounding Matters

Without grounding:
- LLM might suggest non-existent products
- Recommendations may not be compatible
- No guarantee the URLs are real

With grounding:
- Every suggestion is from actual inventory
- Products are pre-vetted for compatibility
- URLs are verified and correct

## API Response Handling

The demo uses OpenAI's Responses API which returns reasoning + output:
- `resp.output[0]` - Reasoning block (thinking process)
- `resp.output[1]` - Actual message with content

The code iterates through the output to find the message with actual content:

```python
for item in resp.output:
    if hasattr(item, "content") and item.content is not None:
        return item.content[0].text
```

This handles both single-output and reasoning-enabled responses.

## Extending the Demo

### Add more scenarios

Modify the `make_prompt()` function to include different use cases:

```python
"project": "Upgrade to 1x12 MTB drivetrain",
"user_bike": {
    "drivetrain_speed": 11,  # upgrading from 11-speed
    "current_cassette": "11-42 MTB cassette",
    ...
}
```

### Filter by product type

In `build_grounding_context()`, add filters before including products:

```python
# Only cassettes under €50
cassettes = [p for p in cassettes if float(p['price'].replace('€', '')) < 50]
```

### Customize the recommendation task

Edit the TASK section in `make_prompt()` to ask for different outputs (e.g., multiple options, cost analysis, installation difficulty).

## Troubleshooting

### `OpenAI API key not found`
- Set `OPENAI_API_KEY` environment variable
- Or pass key when creating client: `OpenAI(api_key="sk-...")`

### `No content found in response`
- Verify the model exists and is accessible
- Check API quota and permissions
- Ensure the prompt is within token limits

### Missing product data
- Verify `data/bc_products_sample.csv` exists
- Run the scraper: `python scrape/cli.py`

## Future Ideas

- [ ] Multi-turn conversation with the LLM
- [ ] Price comparison and budget constraints
- [ ] Seasonal recommendations (summer vs winter tires/gearing)
- [ ] Compatibility checking against user's components
- [ ] Performance metrics (weight, efficiency, cost-per-tooth)
- [ ] User feedback loop to improve recommendations
