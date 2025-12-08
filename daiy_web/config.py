"""Centralized configuration for the Daiy web app."""

# Data
CSV_PATH = "data/bc_products_sample.csv"

# LLM Configuration
LLM_MODEL = "gpt-5-nano"

# Flask app settings
FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5000
FLASK_DEBUG = True

# Candidate selection defaults
DEFAULT_BIKE_SPEED = 11
DEFAULT_USE_CASE = "Road"
MAX_CASSETTES = 5
MAX_CHAINS = 5
