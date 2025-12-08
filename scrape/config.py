"""Configuration and constants for the scraper."""

from typing import Dict

BASE_URL = "https://www.bike-components.de"

# Category URLs to scrape
CATEGORY_URLS: Dict[str, str] = {
    "cassettes": "https://www.bike-components.de/en/components/drivetrain/cassettes/",
    "chains": "https://www.bike-components.de/en/components/drivetrain/chains/",
    "drivetrain_tools": "https://www.bike-components.de/en/tools-maintenance/tools-by-category/drivetrains/",
    "mtb_gloves": "https://www.bike-components.de/en/apparel/mountain-bike-apparel/gloves/",
}

# HTTP headers for polite scraping
HEADERS = {
    "User-Agent": "daiy.de educational scraper (contact: mail@timklausmann.de)",
}

# Request timeouts
REQUEST_TIMEOUT = 15

# Delay between requests (in seconds)
DELAY_MIN = 1.0
DELAY_MAX = 3.0

# Output path
OUTPUT_PATH = "data/bc_products_sample.csv"
