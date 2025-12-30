# Daiy Web App

A Flask-based web interface for AI-powered bike component recommendations with a modern split-panel UI.

## Architecture & Recent Changes (Dec 30, 2025)

### Three-Phase LLM Flow

```
User Input (text + optional image)
           ↓
[Phase 1: Job Identification]
  - LLM generates step-by-step instructions with [category_key] references
  - LLM self-assesses confidence for each technical specification
  - Specs with confidence < 0.8 flagged as "unclear_specifications"
           ↓
  [Decision: Any unclear specs?]
    ├─ NO: Skip to Phase 3
    └─ YES: Show all questions at once (Phase 2)
           ↓
[Phase 2: Clarification (if needed)]
  - Display all unclear questions with:
    • Question text (LLM-generated)
    • Hint (how to find the answer)
    • 2-5 options (multiple choice)
    • "Other" button (custom text)
  - User can answer in any order
  - All answers collected at once
           ↓
[Phase 3: Final Recommendation]
  - LLM receives instructions, answers, and available products
  - Replaces [category_key] with actual product names
  - Returns:
    • final_instructions: Step-by-step with product names
    • primary_products: What user explicitly needs
    • tools: Required for the job
    • optional_extras: Max 3 related items
           ↓
Display Results with Answered Questions
  - Final instructions rendered as numbered steps
  - Products organized by type with per-item reasoning
  - Left panel shows all answered questions as labeled bubbles
```

### What's New (Dec 30, 2025)

#### ✅ Completed
- **Removed legacy clarification flow** - No more hardcoded gearing/use_case dimensions
- **Dynamic clarification questions** - Any spec the LLM identifies can be asked (not just speed/use_case)
- **Answered questions display** - Shows all clarifications answered by user in results view
- **Comprehensive logging** - Every step logged with event types:
  - `user_input` - Initial query + any clarification answers
  - `clarification_required` - Questions being asked
  - `llm_call_*` / `llm_response_*` - All LLM interactions with stage name
  - `recommendation_result` - Final output with summary
- **HTML log viewer** - `view_logs.py` displays logs by session with filters
- **Updated documentation** - FLOW.md with mermaid diagrams and data structures

#### 🔄 Architecture Changes
| Component | Before | After |
|-----------|--------|-------|
| Clarification | Hardcoded gearing + use_case | LLM-identified unclear specs |
| Questions | 2 fixed dimensions | Dynamic, any number |
| Flow | Check dimensions → ask → continue | Ask unclear specs → continue |
| UI Display | Speed/Use case bubbles | All answered questions as bubbles |
| Logging | Old v2/v3 naming | Clean event types with stages |

#### 🔮 Future Enhancements
- **Catalog-wide optional product search** - Currently limited to already-mentioned categories

### Key Files & Changes

| File | Changes |
|------|---------|
| `job_identification.py` | New `UnclearSpecification` class, instructions-based format |
| `api.py` | Removed legacy dimension checking, only uses unclear_specifications |
| `templates/index.html` | Removed ~70 lines of legacy code, dynamic clarification display |
| `view_logs.py` | New handlers for clarification_required and recommendation_result events |
| `FLOW.md` | Complete rewrite with new mermaid diagrams |
| `logging_utils.py` | No changes (already flexible) |

---

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

### Core Modules (Three-Phase Flow)

#### `job_identification.py` - Phase 1: Understand the Job
Analyzes user input to extract what needs to be done:
- `UnclearSpecification` - Represents a spec needing clarification
  - Fields: spec_name, confidence, question, hint, options
  - Used to flag unclear specs (confidence < 0.8)
- `JobIdentification` - Result of job identification
  - `instructions` - List of steps with `[category_key]` placeholders
  - `unclear_specifications` - Array of unclear specs
  - `inferred_values` - Detected specifications (e.g., {"use_case": "road"})
  - `confidence` - Overall confidence (0-1)
  - `reasoning` - Why these categories/specs were detected
- `identify_job()` - Calls LLM with problem text and optional image
- `extract_categories_from_instructions()` - Parses `[category_key]` references

**Key change:** Instructions now contain actual work steps, not category lists.

#### `api.py` - Orchestrate Three Phases
Main API endpoint `/api/recommend` orchestrates all phases:
1. **Phase 1 call** - `identify_job()` to analyze problem
2. **Check clarifications** - Filter unanswered unclear specs
3. **Return if needed** - Send clarification_questions back to frontend
4. **Phase 2 done** - User answers and sends back with `clarification_answers`
5. **Phase 3 call** - `_call_llm_recommendation()` with answers and products
6. **Return results** - final_instructions with primary_products, tools, optional_extras

Also handles:
- Image processing for OpenAI
- Product catalog validation
- Candidate selection for recommendation phase
- Legacy API format support (backward compat)

#### `prompts.py` - LLM Prompt Builders
- `_build_job_identification_prompt()` - Phase 1
  - Asks LLM to generate step-by-step instructions
  - Mentions categories for context (uses `[category_key]` format)
  - Asks LLM to self-assess confidence for each spec
- `build_recommendation_context()` - Assemble Phase 3 context
  - Combines instructions, clarifications, available products
  - Formatted as JSON for LLM parsing
- `_make_recommendation_prompt_new()` - Phase 3 prompt
  - Asks LLM to finalize instructions (replace placeholders)
  - Select primary products, tools, optional extras (max 3)
  - Provide reasoning for each selection

### Supporting Modules

#### `categories.py`
Product category system:
- `PRODUCT_CATEGORIES` - Dict mapping category_key → config
  - display_name, description, fit_dimensions
- `SHARED_FIT_DIMENSIONS` - Common specs across categories
  - gearing, use_case, brake_rotor_diameter, freehub_compatibility, etc.
  - Each has: prompt, hint, options
- Helper functions for category validation and clarification field retrieval

#### `candidate_selection.py`
Product filtering for Phase 3:
- `select_candidates_dynamic()` - Filters products by category + fit values
- Respects `MAX_CHAINS/CASSETTES/TOOLS` limits (from config)
- Returns products ready for LLM recommendation

#### `config.py`
Centralized configuration:
- `LLM_MODEL` - OpenAI model (gpt-4-mini)
- `FLASK_HOST/PORT` - Server settings
- Product data paths and candidate limits

#### `logging_utils.py`
Structured JSONL logging:
- `log_interaction()` - Write timestamped event to log
- LOG_FILE - Path to today's log file
- Event types: user_input, clarification_required, llm_call_*, llm_response_*, recommendation_result, llm_parse_error, llm_error, etc.

#### `view_logs.py`
HTML log viewer:
- Reads JSONL log file
- Groups events by session (user interaction sessions)
- Creates formatted HTML report
- Supports filtering by event type
- Collapsible details for prompts/responses
- Mobile-friendly styling

Usage: `python web/view_logs.py` opens view_logs.html in browser

#### `image_utils.py`
Image processing for OpenAI:
- Validates base64 image format
- Resizes to fit token limits
- Provides image metadata for logging

#### `catalog.py`
Product catalog management:
- Loads CSV product data
- Caches in memory for fast filtering
- Extracts product properties

#### `app.py`
Flask application setup:
- Basic auth (optional demo protection)
- Blueprint registration
- GET `/` serves index.html
- Error handling

#### `templates/index.html`
Single-page web app (~2100 lines):
- **Query Input** - Text + image upload
- **Clarification Panel** - Dynamic question rendering
  - Shows question, hint, options, "Other" button
  - All questions shown at once
  - Updates answered questions display in real-time
- **Results Display** - Two tabs
  - **Products Tab** - Primary products, tools, optional extras
  - **Instructions Tab** - Step-by-step final instructions
- **Answered Questions** - Bubbles showing all clarifications user provided
  - Dynamically populated from selectedValues
  - Shows any spec type (not just speed/use_case)

### App Flow

```
[User Input]
    ↓
identify_job() ──→ LLM Phase 1
    ↓
[Check unclear specs]
    ├─ Yes ──→ Return clarification_questions
    │           ↓
    │         [User selects options]
    │           ↓
    │         [POST /api/recommend again]
    │
    └─ No
        ↓
select_candidates_dynamic() ──→ Get products
        ↓
_call_llm_recommendation() ──→ LLM Phase 3
        ↓
[Return final results]
```

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
2. Enter your project description (e.g., "I need a 12-speed chain for my road bike")
3. Optionally upload a photo of your bike
4. Click submit →
5. **If clarification needed:**
   - Review the preview instructions
   - Answer all clarification questions (hints provided)
   - Click "Get Recommendations"
6. **View results:**
   - **Products Tab** - Primary products with reasoning, tools, optional extras
   - **Instructions Tab** - Step-by-step instructions with product names
   - **Answered Questions** - Bubbles showing what you clarified

### API Endpoints

#### POST `/api/recommend` - Main Recommendation Flow

**Phase 1 - Initial Request:**
```json
{
  "problem_text": "I need a new 12-speed chain for my road bike",
  "image_base64": null
}
```

**Phase 2 - Response with Clarification Questions:**
```json
{
  "need_clarification": true,
  "job": {
    "instructions": [
      "Step 1: Remove old chain using chain tool [drivetrain_tools]",
      "Step 2: Install new Shimano [drivetrain_chains] chain"
    ],
    "unclear_specifications": [
      {
        "spec_name": "use_case",
        "confidence": 0.4,
        "question": "What type of riding do you do?",
        "hint": "Road, mountain, commuting, touring?",
        "options": ["road", "mountain", "commuting", "touring"]
      }
    ]
  },
  "clarification_questions": [/* same as unclear_specifications */],
  "instructions_preview": ["Step 1: Remove old chain...", "Step 2: Install new chain..."],
  "inferred_values": {"gearing": 12}
}
```

**User Answers & Follow-up Request:**
```json
{
  "problem_text": "I need a new 12-speed chain for my road bike",
  "clarification_answers": [
    {"spec_name": "use_case", "answer": "road"}
  ],
  "identified_job": {...}  // From previous response
}
```

**Phase 3 - Final Response with Products:**
```json
{
  "diagnosis": "12-speed chain replacement for road bike",
  "final_instructions": [
    "Step 1: Use Park Tool CT-3.2 chain tool to remove old Shimano CN-M7000 chain",
    "Step 2: Install new Shimano CN-M8100 12-speed chain",
    "Step 3: Connect with quick-link, ensuring proper direction"
  ],
  "primary_products": [
    {
      "category": "drivetrain_chains",
      "category_display": "Chains",
      "product": {
        "name": "Shimano CN-M8100",
        "brand": "Shimano",
        "price": "$29.99",
        "url": "https://bike-components.de/..."
      },
      "reasoning": "12-speed chain compatible with Shimano drivetrain and road use"
    }
  ],
  "tools": [
    {
      "category": "drivetrain_tools",
      "category_display": "Tools",
      "product": {
        "name": "Park Tool CT-3.2",
        "brand": "Park Tool",
        "price": "$24.99",
        "url": "https://bike-components.de/..."
      },
      "reasoning": "Required to safely remove and install chain"
    }
  ],
  "optional_extras": [
    {
      "category": "drivetrain_cassettes",
      "category_display": "Cassettes",
      "product": {...},
      "reasoning": "Worn chains often damage cassettes - consider replacing together"
    }
  ],
  "fit_values": {"gearing": 12, "use_case": "road"}
}
```

**Key Differences from Phase 2:**
- `final_instructions` replaces `[category_key]` with actual product names
- `primary_products`, `tools`, `optional_extras` - organized by purpose
- Each product includes per-item `reasoning`
- Max 3 `optional_extras` from already-mentioned categories

#### GET `/api/categories` - List Categories

**Response:**
```json
{
  "categories": [
    {
      "key": "drivetrain_chains",
      "display_name": "Chains",
      "description": "Bicycle chains for different speeds",
      "fit_dimensions": ["gearing", "use_case"]
    },
    {
      "key": "drivetrain_tools",
      "display_name": "Drivetrain Tools",
      "description": "Tools for chain, cassette, and drivetrain work",
      "fit_dimensions": []
    }
  ]
}
```

---

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
