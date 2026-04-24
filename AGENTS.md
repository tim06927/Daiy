# Repository Guidelines

## Project Structure & Module Organization

Daiy is a Python/Flask application with a shared SQLite product database. Core web code lives in `web/`: `app.py` configures Flask, `api.py` orchestrates recommendations, and `catalog.py`, `candidate_selection.py`, `job_identification.py`, and `prompts.py` handle the LLM/product flow. Frontend assets are plain files under `web/static/css/` and `web/static/js/`, with templates in `web/templates/`.

Scraping code lives in `scrape/`, including the CLI, parser, database helpers, discovery workflows, and scraper tests. Data lives in `data/`, especially `data/products.db`. Web tests are in `web/tests/`; scraper tests are in `scrape/tests/`.

## Build, Test, and Development Commands

- `pip install -r requirements.txt`: install pinned runtime and development dependencies.
- `make setup`: create `.env` from `.env.example` if missing.
- `make run-dev`: run the Flask development server via `python -m web.app`.
- `make run`: run the app with gunicorn on port 5000.
- `pytest` or `pytest web/tests -v`: run the configured web test suite.
- `pytest scrape/tests -v`: run scraper tests, which are outside the default pytest path.
- `make scrape MAX_PAGES=5`: run an incremental, polite scrape into `data/products.db`.

## Coding Style & Naming Conventions

Use Python 3.9+ with 4-space indentation, type hints on functions, and docstrings for public functions. Follow PEP 8 import ordering. Use `snake_case` for functions/variables, `UPPER_CASE` for constants, and `_leading_underscore` for private helpers. Black and Ruff are configured in `pyproject.toml` with line length 100; run `black web scrape` and `ruff check web scrape` before larger changes.

## Testing Guidelines

Tests use pytest. Name files `test_*.py`, classes `Test*`, and functions `test_*`. Prefer focused unit tests for parsing, candidate selection, privacy, and API behavior. Some vision/model tests may require `OPENAI_API_KEY` and network access, so run targeted tests when offline. The app and tests may write logs, errors, or interactions into `data/products.db`.

## Commit & Pull Request Guidelines

Git history uses short, direct commit summaries such as `Update README for version 0.3.0 features` and `Added Tips feature during wait time`; keep messages concise and action-oriented. For pull requests, include a clear description, test commands run, linked issues if relevant, screenshots for UI changes, and notes about database, scraper, or environment changes.

## Security & Configuration Tips

Never commit API keys or credentials. Use `.env` for `OPENAI_API_KEY`, `FLASK_SECRET_KEY`, and optional `DEMO_USER`/`DEMO_PASS`. Preserve scraper politeness settings and the identifying User-Agent. Keep LLM recommendations grounded in products returned from `data/products.db`; do not add flows that invent product inventory.
