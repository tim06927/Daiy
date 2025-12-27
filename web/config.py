"""Centralized configuration for the Daiy web app."""

import os
from pathlib import Path

# Determine project root (parent of 'web' directory)
_THIS_DIR = Path(__file__).parent
_PROJECT_ROOT = _THIS_DIR.parent

# Data - use absolute path for consistent loading
CSV_PATH = str(_PROJECT_ROOT / "data" / "bc_products_sample.csv")

# LLM Configuration
LLM_MODEL = "gpt-5.2"

# Flask app settings (allow env overrides; default debug off for safety)
# Render sets PORT dynamically; fall back to FLASK_PORT or 5000 for local.
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", os.getenv("PORT", "5000")))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"

# Candidate selection limits (per category)
MAX_PRODUCTS_PER_CATEGORY = int(os.getenv("MAX_PRODUCTS_PER_CATEGORY", "5"))

# Legacy config - kept for backward compatibility, will be removed
MAX_CASSETTES = int(os.getenv("MAX_CASSETTES", str(MAX_PRODUCTS_PER_CATEGORY)))
MAX_CHAINS = int(os.getenv("MAX_CHAINS", str(MAX_PRODUCTS_PER_CATEGORY)))
MAX_TOOLS = int(os.getenv("MAX_TOOLS", str(MAX_PRODUCTS_PER_CATEGORY)))

# UI Settings
SHOW_DEMO_NOTICE = os.getenv("SHOW_DEMO_NOTICE", "True").lower() == "true"
