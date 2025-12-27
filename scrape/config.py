"""Configuration and constants for the scraper."""

from typing import Any, Dict, Optional

__all__ = [
    "BASE_URL",
    "CATEGORY_URLS",
    "HEADERS",
    "REQUEST_TIMEOUT",
    "DELAY_MIN",
    "DELAY_MAX",
    "DELAY_OVERNIGHT_MIN",
    "DELAY_OVERNIGHT_MAX",
    "MAX_RETRIES",
    "RETRY_BACKOFF_BASE",
    "RETRY_STATUS_CODES",
    "MAX_PAGES_PER_CATEGORY",
    "DEFAULT_MAX_PAGES",
    "OUTPUT_PATH",
    "DB_PATH",
    "CATEGORY_SPECS",
    "get_spec_config",
]

BASE_URL = "https://www.bike-components.de"

# Category URLs to scrape
CATEGORY_URLS: Dict[str, str] = {
    "cassettes": "https://www.bike-components.de/en/components/drivetrain/cassettes/",
    "chains": "https://www.bike-components.de/en/components/drivetrain/chains/",
    "drivetrain_tools": "https://www.bike-components.de/en/tools-maintenance/tools-by-category/drivetrains/",
    "mtb_gloves": "https://www.bike-components.de/en/apparel/mountain-bike-apparel/gloves/",
    "shifters_derailleurs": "https://www.bike-components.de/en/tools-maintenance/tools-by-category/shifters-derailleurs/",
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

# Overnight mode delays - much slower to minimize server load
# Suitable for unattended overnight runs
DELAY_OVERNIGHT_MIN = 10.0
DELAY_OVERNIGHT_MAX = 30.0

# Retry settings with exponential backoff
MAX_RETRIES = 5  # Maximum retry attempts
RETRY_BACKOFF_BASE = 2.0  # Base for exponential backoff (2^attempt seconds)
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}  # Status codes to retry on

# Pagination settings
MAX_PAGES_PER_CATEGORY = 50  # Safety limit to avoid runaway scraping
DEFAULT_MAX_PAGES = 10  # Default when not specified

# Output paths
OUTPUT_PATH = "data/bc_products_sample.csv"
DB_PATH = "data/products.db"


# =============================================================================
# Category-Specific Spec Field Definitions
# =============================================================================
# Each category maps to:
#   - spec_table: The SQLite table name for category-specific fields
#   - field_mappings: Dict mapping DB column -> list of possible HTML spec labels

CategorySpecConfig = Dict[str, Any]

CATEGORY_SPECS: Dict[str, CategorySpecConfig] = {
    "chains": {
        "spec_table": "chain_specs",
        "field_mappings": {
            "application": ["Application", "Einsatzbereich"],
            "gearing": ["Gearing", "Schaltstufen hinten", "Speed", "Speeds"],
            "num_links": ["Number of Links", "Kettenlänge", "Links"],
            "closure_type": ["Closure Type", "Verschlussart"],
            "pin_type": ["Pin Type", "Nietentyp"],
            "directional": ["Directional", "Laufrichtungsgebunden"],
            "material": ["Material"],
        },
    },
    "cassettes": {
        "spec_table": "cassette_specs",
        "field_mappings": {
            "application": ["Application", "Einsatzbereich"],
            "gearing": ["Gearing", "Speeds", "Speed", "Schaltstufen"],
            "gradation": ["Gradation", "Cog Range", "Sprocket Range", "Ritzelabstufung"],
            "sprocket_material": ["Sprocket Material", "Material"],
            "freehub_compatibility": ["Freehub Compatibility", "Freehub Body", "Freilaufkörper"],
            "recommended_chain": ["Recommended Chain"],
            "series": ["Series"],
            "shifter": ["Shifter"],
            "ebike": ["E-Bike"],
        },
    },
    "mtb_gloves": {
        "spec_table": "glove_specs",
        "field_mappings": {
            "size": ["Size", "Größe"],
            "material": ["Material", "Upper Material", "Obermaterial"],
            "padding": ["Padding", "Polsterung", "Palm Padding"],
            "closure": ["Closure", "Verschluss"],
            "touchscreen": ["Touchscreen", "Touchscreen Compatible", "Smartphone Compatible"],
            "season": ["Season", "Saison", "Recommended Use"],
        },
    },
    "drivetrain_tools": {
        "spec_table": "tool_specs",
        "field_mappings": {
            "tool_type": ["Type", "Tool Type", "Werkzeugtyp"],
            "compatibility": ["Compatibility", "Kompatibilität", "Compatible With"],
            "material": ["Material"],
            "weight": ["Weight", "Gewicht"],
        },
    },
    "shifters_derailleurs": {
        "spec_table": "tool_specs",
        "field_mappings": {
            "tool_type": ["Type", "Tool Type", "Werkzeugtyp"],
            "compatibility": ["Compatibility", "Kompatibilität", "Compatible With"],
            "material": ["Material"],
            "weight": ["Weight", "Gewicht"],
        },
    },
}


def get_spec_config(category: str) -> Optional[CategorySpecConfig]:
    """Get the spec configuration for a category."""
    return CATEGORY_SPECS.get(category)
