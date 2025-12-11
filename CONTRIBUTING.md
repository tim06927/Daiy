# Contributing to Daiy

Thanks for your interest in contributing to Daiy! This document provides guidelines and instructions for getting involved.

## Code of Conduct

Be respectful, inclusive, and constructive in all interactions.

## Getting Started

### Prerequisites
- Python 3.9+
- Virtual environment (`venv` or `conda`)
- OpenAI API key (for LLM features)

### Local Setup

```bash
# Clone the repository
git clone https://github.com/tim06927/daiy.git
cd daiy

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
```

## Development Workflow

### Coding Standards

We follow these conventions to keep the codebase clean and readable:

1. **Type Hints**: All functions must have type hints on parameters and return values
   ```python
   def calculate_gear_range(speed: int, cog_max: int) -> float:
       return cog_max / speed
   ```

2. **Docstrings**: All public functions need docstrings with Args, Returns, and Raises sections
   ```python
   def fetch_products(url: str) -> List[Product]:
       """Fetch bike components from the specified URL.
       
       Args:
           url: Target website URL to scrape.
       
       Returns:
           List of Product objects found on the page.
       
       Raises:
           requests.RequestException: If the HTTP request fails.
       """
   ```

3. **Import Organization**: Follow PEP 8 ordering
   ```python
   import json
   import logging
   from typing import Dict, List
   
   import pandas as pd
   import requests
   
   from scrape.models import Product
   ```

4. **Naming**:
   - Functions and variables: `snake_case`
   - Constants: `UPPER_CASE`
   - Private functions: `_leading_underscore`
   - Descriptive names: `extract_sku()` not `get_value()`

5. **Error Handling**: Catch specific exceptions, never bare `except:`
   ```python
   try:
       data = json.loads(response)
   except json.JSONDecodeError:
       logger.error("Invalid JSON response")
       return None
   except requests.RequestException as e:
       logger.error(f"Request failed: {e}")
       raise
   ```

### Code Review Checklist

Before submitting a pull request, ensure:

- [ ] Code follows the style guide above
- [ ] All functions have type hints
- [ ] All public functions have docstrings
- [ ] No unused imports
- [ ] No hardcoded API keys or credentials
- [ ] Configuration uses `config.py` files
- [ ] Code is readable and maintainable
- [ ] Comments explain WHY, not WHAT
- [ ] Tests added for new features
- [ ] README updated if behavior changes

### Running Tests

```bash
pytest tests/
pytest --cov=scrape,grounded_demo,web  # with coverage
```

### Code Quality Tools

```bash
# Format code with Black
black scrape/ grounded_demo/ web/

# Lint with Ruff
ruff check scrape/ grounded_demo/ web/

# Type checking
mypy scrape/ grounded_demo/ web/
```

## Project Structure

```
daiy/
├── scrape/              # Web scraper for bike components
│   ├── __init__.py
│   ├── config.py       # URLs, headers, output paths
│   ├── models.py       # Product dataclass
│   ├── html_utils.py   # Parsing utilities
│   ├── scraper.py      # Core scraping logic
│   ├── csv_utils.py    # CSV I/O functions
│   ├── cli.py          # Command-line interface
│   └── README.md
├── grounded_demo/       # Proof-of-concept CLI demo
│   ├── demo.py
│   ├── catalog.py
│   └── README.md
├── web/           # Flask web application
│   ├── app.py
│   ├── config.py
│   ├── templates/
│   └── README.md
├── requirements.txt    # Python dependencies
├── README.md          # Project overview
└── pyproject.toml     # Project metadata
```

## Key Concepts

### Grounding
The core principle: LLM recommendations must come from real, available products in our inventory. This prevents hallucination and ensures practical, actionable advice.

### Incremental Scraping
The scraper can run in two modes:
- **incremental**: Add new products, skip URLs already in CSV
- **full**: Rebuild entire CSV from scratch

Configuration in `scrape/config.py` controls delays (be polite!) and output paths.

## Submitting Changes

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make your changes with good commit messages
3. Push to your fork: `git push origin feature/my-feature`
4. Open a Pull Request with a clear description
5. Address code review feedback

## Questions?

Open an issue on GitHub with the `question` label, or check existing documentation in the README files.

---

Happy coding! We appreciate your contributions to making Daiy better.
