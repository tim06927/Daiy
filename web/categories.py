"""Product category registry for dynamic recommendation flow.

This module dynamically discovers available product categories from the database
and provides fit dimensions for filtering. Categories are auto-generated at startup
from the actual product data, ensuring the LLM always knows about available products.

Special category overrides (e.g., for gearing-based filtering) are defined below
and merged with auto-discovered categories.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

# Handle imports for both direct execution and package import
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).parent))
    from config import CSV_PATH
else:
    from .config import CSV_PATH

logger = logging.getLogger(__name__)

__all__ = [
    "PRODUCT_CATEGORIES",
    "get_category_config",
    "get_all_category_names",
    "get_all_categories",
    "get_fit_dimensions_for_categories",
    "get_clarification_fields",
    "get_categories_for_prompt",
    "SHARED_FIT_DIMENSIONS",
    "refresh_categories",
]


# =============================================================================
# Shared Fit Dimensions
# =============================================================================
# Dimensions that may be shared across multiple categories.
# When building clarification prompts, we can consolidate questions
# for dimensions shared across selected categories.

SHARED_FIT_DIMENSIONS = {
    "gearing": {
        "display_name": "Drivetrain Speed",
        "prompt": "What speed drivetrain do you have?",
        "hint": "Count the cogs on your rear cassette, or check the number printed on your shifter (e.g., '11' for 11-speed).",
        "options": ["8-speed", "9-speed", "10-speed", "11-speed", "12-speed"],
        "parser": lambda v: int(v.replace("-speed", "")) if isinstance(v, str) else v,
        "filter_column": "speed",  # Column name in the catalog DataFrame
    },
    "use_case": {
        "display_name": "Riding Style",
        "prompt": "What type of riding will you do?",
        "hint": "Think about where you ride most: smooth roads, gravel paths, mountain trails, or city commutes.",
        "options": ["road", "gravel", "mtb", "commute", "touring", "e-bike"],
        "parser": lambda v: v.lower().strip() if isinstance(v, str) else v,
        "filter_column": "application",  # Column name in the catalog DataFrame
    },
    "size": {
        "display_name": "Size",
        "prompt": "What size do you need?",
        "hint": "Check the size chart or measure according to product guidelines.",
        "options": ["XS", "S", "M", "L", "XL", "XXL"],
        "parser": lambda v: v.upper().strip() if isinstance(v, str) else v,
        "filter_column": "size",
    },
    "season": {
        "display_name": "Season",
        "prompt": "What season or temperature range will you use this?",
        "hint": "Summer gear is lighter and breathable, winter gear has insulation.",
        "options": ["Summer", "All-Season", "Winter"],
        "parser": lambda v: v.title().strip() if isinstance(v, str) else v,
        "filter_column": "season",
    },
    "freehub_compatibility": {
        "display_name": "Freehub Type",
        "prompt": "What type of freehub does your wheel have?",
        "hint": "Common types: Shimano/SRAM HG (most common), SRAM XD, Shimano Micro Spline, Campagnolo.",
        "options": ["Shimano/SRAM HG", "SRAM XD", "Shimano Micro Spline", "Campagnolo"],
        "parser": lambda v: v.strip() if isinstance(v, str) else v,
        "filter_column": "freehub_compatibility",
    },
}


# =============================================================================
# Category Override Configs
# =============================================================================
# Special configurations for categories that need custom handling (e.g., gearing).
# These are merged with auto-discovered categories from the database.

CATEGORY_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "drivetrain_cassettes": {
        "display_name": "Cassettes",
        "description": "Rear gear clusters for bicycles",
        "fit_dimensions": ["gearing", "use_case", "freehub_compatibility"],
        "required_fit": ["gearing"],
        "optional_fit": ["use_case", "freehub_compatibility"],
        "filter_strategy": "strict",
        "max_results": 5,
    },
    "drivetrain_chains": {
        "display_name": "Chains",
        "description": "Bicycle drive chains connecting crankset to cassette",
        "fit_dimensions": ["gearing", "use_case"],
        "required_fit": ["gearing"],
        "optional_fit": ["use_case"],
        "filter_strategy": "strict",
        "max_results": 5,
    },
    "drivetrain_cranks": {
        "display_name": "Cranksets",
        "description": "Cranksets and crank arms",
        "fit_dimensions": ["gearing", "use_case"],
        "required_fit": [],
        "optional_fit": ["gearing", "use_case"],
        "filter_strategy": "fuzzy",
        "max_results": 5,
    },
    "drivetrain_chainrings": {
        "display_name": "Chainrings",
        "description": "Front chainrings for various drivetrain setups",
        "fit_dimensions": ["gearing", "use_case"],
        "required_fit": [],
        "optional_fit": ["gearing", "use_case"],
        "filter_strategy": "fuzzy",
        "max_results": 5,
    },
}


# =============================================================================
# Category Key Patterns → Fit Dimensions
# =============================================================================
# Patterns to auto-assign fit dimensions based on category key.
# Order matters - first match wins.

CATEGORY_DIMENSION_PATTERNS = [
    # Drivetrain components that need gearing
    (["cassettes", "chains", "chainrings", "cranks", "derailleurs", "shifters"], 
     ["gearing", "use_case"]),
    # Apparel needs size and season
    (["apparel", "jerseys", "jackets", "pants", "shorts", "gloves", "socks"],
     ["size", "season", "use_case"]),
    # Footwear needs size
    (["shoes", "boots"],
     ["size", "use_case"]),
    # Components that benefit from use_case filtering
    (["saddles", "handlebars", "stems", "grips", "pedals", "wheels", "tyres", "tires"],
     ["use_case"]),
    # Tools and accessories - usually universal
    (["tools", "accessories", "bags", "bottles", "pumps", "lights", "locks"],
     []),
]


def _infer_fit_dimensions(category_key: str) -> List[str]:
    """Infer appropriate fit dimensions from category key patterns."""
    key_lower = category_key.lower()
    for patterns, dimensions in CATEGORY_DIMENSION_PATTERNS:
        if any(pattern in key_lower for pattern in patterns):
            return dimensions
    return []  # Default: no fit dimensions


def _generate_display_name(category_key: str) -> str:
    """Generate human-readable display name from category key."""
    # Remove common prefixes and convert to title case
    name = category_key
    for prefix in ["drivetrain_", "components_", "accessories_", "apparel_", "tools_"]:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return name.replace("_", " ").title()


def _generate_description(category_key: str, product_count: int) -> str:
    """Generate description from category key."""
    display = _generate_display_name(category_key)
    return f"{display} - {product_count} products available"


def _create_default_category_config(
    category_key: str, 
    product_count: int
) -> Dict[str, Any]:
    """Create a default category configuration."""
    fit_dims = _infer_fit_dimensions(category_key)
    
    return {
        "display_name": _generate_display_name(category_key),
        "description": _generate_description(category_key, product_count),
        "fit_dimensions": fit_dims,
        "required_fit": [],  # Default: no required dimensions
        "optional_fit": fit_dims,
        "filter_strategy": "fuzzy",
        "max_results": 5,
        "product_count": product_count,  # Track for diagnostics
    }


def discover_categories_from_catalog(csv_path: str = CSV_PATH) -> Dict[str, Dict[str, Any]]:
    """Discover all categories from the product catalog.
    
    Reads the CSV/database and extracts unique categories with product counts.
    Merges with CATEGORY_OVERRIDES for special handling.
    
    Args:
        csv_path: Path to the product catalog CSV.
        
    Returns:
        Dict mapping category key to category configuration.
    """
    categories: Dict[str, Dict[str, Any]] = {}
    
    try:
        # Load catalog (low_memory=False to avoid dtype warnings with many columns)
        df = pd.read_csv(csv_path, low_memory=False)
        
        # Get category counts
        if "category" not in df.columns:
            logger.error(
                "CRITICAL: No 'category' column found in product catalog. "
                f"Available columns: {list(df.columns)}. "
                f"Falling back to {len(CATEGORY_OVERRIDES)} override categories only."
            )
            return dict(CATEGORY_OVERRIDES)
        
        category_counts = df["category"].value_counts().to_dict()
        
        logger.info(f"Discovered {len(category_counts)} categories from catalog")
        
        # Create config for each category
        for cat_key, count in category_counts.items():
            if pd.isna(cat_key) or not cat_key:
                continue
                
            # Use override if available, otherwise generate default
            if cat_key in CATEGORY_OVERRIDES:
                config = dict(CATEGORY_OVERRIDES[cat_key])
                config["product_count"] = count
            else:
                config = _create_default_category_config(cat_key, count)
            
            categories[cat_key] = config
        
        # Add any overrides that aren't in the catalog (shouldn't happen, but safe)
        for cat_key, config in CATEGORY_OVERRIDES.items():
            if cat_key not in categories:
                categories[cat_key] = dict(config)
                categories[cat_key]["product_count"] = 0
                
    except FileNotFoundError:
        logger.error(
            f"CRITICAL: Product catalog not found at {csv_path}. "
            f"The application will have limited functionality with only "
            f"{len(CATEGORY_OVERRIDES)} override categories available. "
            f"Please ensure the CSV file exists before starting the app."
        )
        categories = dict(CATEGORY_OVERRIDES)
    except Exception as e:
        logger.error(
            f"CRITICAL: Error discovering categories: {e}. "
            f"Falling back to {len(CATEGORY_OVERRIDES)} override categories only. "
            f"This may cause unexpected behavior."
        )
        categories = dict(CATEGORY_OVERRIDES)
    
    return categories


# =============================================================================
# Initialize Categories at Module Load
# =============================================================================

PRODUCT_CATEGORIES: Dict[str, Dict[str, Any]] = discover_categories_from_catalog()


def refresh_categories(csv_path: str = CSV_PATH) -> None:
    """Refresh the category registry from the catalog.
    
    Call this after updating the product database to pick up new categories.
    """
    global PRODUCT_CATEGORIES
    PRODUCT_CATEGORIES = discover_categories_from_catalog(csv_path)
    logger.info(f"Refreshed categories: {len(PRODUCT_CATEGORIES)} available")


# =============================================================================
# Helper Functions
# =============================================================================


def get_category_config(category: str) -> Optional[Dict[str, Any]]:
    """Get configuration for a specific category.
    
    Args:
        category: Category key (e.g., "saddles_road_saddles", "drivetrain_chains").
        
    Returns:
        Category configuration dict or None if not found.
    """
    return PRODUCT_CATEGORIES.get(category)


def get_all_category_names() -> List[str]:
    """Get list of all available category keys.
    
    Returns:
        List of category keys.
    """
    return list(PRODUCT_CATEGORIES.keys())


def get_all_categories() -> List[str]:
    """Alias for get_all_category_names for API compatibility."""
    return get_all_category_names()


def get_fit_dimensions_for_categories(categories: List[str]) -> Dict[str, Dict[str, Any]]:
    """Get consolidated fit dimensions for a set of categories.
    
    Combines fit dimensions across all requested categories, marking which
    dimensions are required vs optional.
    
    Args:
        categories: List of category keys.
        
    Returns:
        Dict mapping dimension name to config with added 'is_required' field.
    """
    result: Dict[str, Dict[str, Any]] = {}
    
    for cat in categories:
        config = PRODUCT_CATEGORIES.get(cat)
        if not config:
            continue
            
        for dim in config.get("fit_dimensions", []):
            if dim not in SHARED_FIT_DIMENSIONS:
                continue
                
            if dim not in result:
                result[dim] = {
                    **SHARED_FIT_DIMENSIONS[dim],
                    "is_required": dim in config.get("required_fit", []),
                    "categories": [cat],
                }
            else:
                # Merge: if required for ANY category, mark as required
                result[dim]["categories"].append(cat)
                if dim in config.get("required_fit", []):
                    result[dim]["is_required"] = True
                    
    return result


def get_clarification_fields(
    categories: List[str],
    already_known: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """Get clarification fields needed for the given categories.
    
    Filters out dimensions that are already known (from user input or LLM inference).
    
    Args:
        categories: List of category keys.
        already_known: Dict of already-known dimension values.
        
    Returns:
        Dict mapping dimension name to clarification config for missing dimensions.
    """
    all_dims = get_fit_dimensions_for_categories(categories)
    
    return {
        dim: config
        for dim, config in all_dims.items()
        if dim not in already_known or already_known.get(dim) is None
    }


def get_categories_for_prompt(max_categories: int = 100) -> str:
    """Generate a prompt-friendly description of available categories.
    
    Groups categories by top-level type for better LLM comprehension.
    
    Args:
        max_categories: Maximum number of categories to include (for token limits).
        
    Returns:
        Formatted string describing available categories for LLM context.
    """
    # Group categories by prefix
    groups: Dict[str, List[tuple]] = {}
    
    for key, config in PRODUCT_CATEGORIES.items():
        # Get top-level group (first part of key)
        parts = key.split("_")
        group = parts[0] if parts else "other"
        
        if group not in groups:
            groups[group] = []
        groups[group].append((key, config.get("display_name", key)))
    
    # Build prompt with grouped categories
    lines = ["Available product categories (use exact keys in [brackets]):"]
    lines.append("")
    
    category_count = 0
    for group_name in sorted(groups.keys()):
        if category_count >= max_categories:
            break
            
        group_items = groups[group_name]
        lines.append(f"**{group_name.title()}:**")
        
        for key, display_name in sorted(group_items, key=lambda x: x[1]):
            if category_count >= max_categories:
                break
            lines.append(f"  - {key}: {display_name}")
            category_count += 1
        
        lines.append("")
    
    if len(PRODUCT_CATEGORIES) > max_categories:
        lines.append(f"  ... and {len(PRODUCT_CATEGORIES) - max_categories} more categories")
    
    return "\n".join(lines)
