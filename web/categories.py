"""Product category registry for dynamic recommendation flow.

This module defines available product categories and their fit dimensions,
enabling the app to handle any combination of categories without hardcoding.
"""

from typing import Any, Dict, List, Optional

__all__ = [
    "PRODUCT_CATEGORIES",
    "get_category_config",
    "get_all_category_names",
    "get_fit_dimensions_for_categories",
    "get_clarification_fields",
    "SHARED_FIT_DIMENSIONS",
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
# Product Category Definitions
# =============================================================================
# Each category defines:
#   - display_name: Human-readable name for UI
#   - description: Short description for job identification context
#   - fit_dimensions: List of fit dimensions from SHARED_FIT_DIMENSIONS
#   - required_fit: Dimensions that MUST be clarified before recommendation
#   - optional_fit: Dimensions that help narrow results but aren't required
#   - filter_strategy: How to filter products ("strict" = exact match, "fuzzy" = substring)
#   - max_results: Maximum products to return per category

PRODUCT_CATEGORIES: Dict[str, Dict[str, Any]] = {
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
    "drivetrain_tools": {
        "display_name": "Drivetrain Tools",
        "description": "Tools for drivetrain maintenance (chain breakers, cassette tools, etc.)",
        "fit_dimensions": ["use_case"],
        "required_fit": [],  # Tools are generally universal
        "optional_fit": ["use_case"],
        "filter_strategy": "fuzzy",
        "max_results": 5,
    },
    "drivetrain_pedals": {
        "display_name": "Pedals",
        "description": "Bicycle pedals including clipless and platform",
        "fit_dimensions": ["use_case"],
        "required_fit": [],
        "optional_fit": ["use_case"],
        "filter_strategy": "fuzzy",
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
    "drivetrain_bottom_brackets": {
        "display_name": "Bottom Brackets",
        "description": "Bottom bracket bearings and cups",
        "fit_dimensions": [],
        "required_fit": [],
        "optional_fit": [],
        "filter_strategy": "fuzzy",
        "max_results": 5,
    },
    "lighting_bicycle_lights_battery": {
        "display_name": "Battery Lights",
        "description": "Battery-powered bicycle lights",
        "fit_dimensions": [],
        "required_fit": [],
        "optional_fit": [],
        "filter_strategy": "fuzzy",
        "max_results": 5,
    },
    "lighting_bicycle_lights_dynamo": {
        "display_name": "Dynamo Lights",
        "description": "Dynamo-powered bicycle lights",
        "fit_dimensions": [],
        "required_fit": [],
        "optional_fit": [],
        "filter_strategy": "fuzzy",
        "max_results": 5,
    },
}


# =============================================================================
# Helper Functions
# =============================================================================


def get_category_config(category: str) -> Optional[Dict[str, Any]]:
    """Get configuration for a specific category.
    
    Args:
        category: Category key (e.g., "cassettes", "chains").
        
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


def get_categories_for_prompt() -> str:
    """Generate a prompt-friendly description of available categories.
    
    Returns:
        Formatted string describing available categories for LLM context.
    """
    lines = ["Available product categories:"]
    for key, config in PRODUCT_CATEGORIES.items():
        lines.append(f"  - {key}: {config['description']}")
    return "\n".join(lines)
