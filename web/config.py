"""Centralized configuration for the Daiy web app."""

import os
from pathlib import Path
from typing import Dict, List

# Determine project root (parent of 'web' directory)
_THIS_DIR = Path(__file__).parent
_PROJECT_ROOT = _THIS_DIR.parent

# LLM Configuration
# Default model (can be overridden per-request)
LLM_MODEL = "gpt-5.2"

# Default model and effort for user-facing requests
DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_EFFORT = "low"

# Available models and their supported effort levels
MODEL_EFFORT_LEVELS: Dict[str, List[str]] = {
    "gpt-5.2": ["none", "low", "medium", "high", "xhigh"],
    "gpt-5-mini": ["minimal", "low", "medium", "high"],
    "gpt-5-nano": ["minimal", "low", "medium", "high"],
}

# All available models
AVAILABLE_MODELS = list(MODEL_EFFORT_LEVELS.keys())


def get_effort_levels_for_model(model: str) -> List[str]:
    """Get valid effort levels for a given model.
    
    Args:
        model: Model name.
        
    Returns:
        List of valid effort levels, or empty list if model not found.
    """
    return MODEL_EFFORT_LEVELS.get(model, [])


def is_valid_model_effort(model: str, effort: str) -> bool:
    """Validate that a model/effort combination is valid.
    
    Args:
        model: Model name.
        effort: Effort level.
        
    Returns:
        True if the combination is valid.
    """
    return model in MODEL_EFFORT_LEVELS and effort in MODEL_EFFORT_LEVELS[model]

# Flask app settings (allow env overrides; default debug off for safety)
# Render sets PORT dynamically; fall back to FLASK_PORT or 5000 for local.
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", os.getenv("PORT", "5000")))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"

# Candidate selection limits (per category)
MAX_PRODUCTS_PER_CATEGORY = int(os.getenv("MAX_PRODUCTS_PER_CATEGORY", "5"))
