"""Dynamic candidate selection for product recommendations.

This module provides category-agnostic product filtering based on
fit dimensions, using database queries for memory efficiency.
"""

import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

# Handle imports for both direct execution and package import
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).parent))
    from categories import (
        PRODUCT_CATEGORIES,
        SHARED_FIT_DIMENSIONS,
        get_category_config,
    )
    from catalog import query_products
else:
    from .categories import (
        PRODUCT_CATEGORIES,
        SHARED_FIT_DIMENSIONS,
        get_category_config,
    )
    from .catalog import query_products

__all__ = [
    "select_candidates_dynamic",
    "apply_fit_filter",
    "prepare_product_for_response",
]

logger = logging.getLogger(__name__)

def _clean_value(value: Any) -> Any:
    """Convert pandas NA values to None while leaving other types intact."""
    try:
        return None if pd.isna(value) else value
    except TypeError:
        return value


def _normalize_image_url(value: Any) -> Optional[str]:
    """Normalize image URLs from the catalog for browser use."""
    cleaned = _clean_value(value)
    if not cleaned:
        return None
    if not isinstance(cleaned, str):
        return None

    url = cleaned.strip()
    if not url:
        return None

    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("/"):
        return f"{_IMAGE_BASE_URL}{url}"
    if not re.match(r"^https?://", url):
        return f"https://{url}"
    return url

_IMAGE_BASE_URL = "https://www.bike-components.de"


def _parse_gearing_value(value: Any) -> Optional[int]:
    """Parse a gearing/speed value to an integer.
    
    Handles formats like: 11, "11", "11-speed", "11s"
    
    Args:
        value: Raw gearing value.
        
    Returns:
        Integer speed value or None.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if not pd.isna(value) else None
    if isinstance(value, str):
        # Extract numeric part
        match = re.search(r"(\d{1,2})", value)
        if match:
            return int(match.group(1))
    return None


def apply_fit_filter(
    df: pd.DataFrame,
    dimension: str,
    value: Any,
    strategy: str = "strict",
) -> pd.DataFrame:
    """Apply a fit dimension filter to a DataFrame.
    
    Args:
        df: Product DataFrame.
        dimension: Fit dimension name (e.g., "gearing", "use_case").
        value: Value to filter for.
        strategy: "strict" for exact match, "fuzzy" for substring match.
        
    Returns:
        Filtered DataFrame.
    """
    if value is None or df.empty:
        return df
    
    dim_config = SHARED_FIT_DIMENSIONS.get(dimension)
    if not dim_config:
        logger.warning(f"Unknown fit dimension: {dimension}")
        return df
    
    column = dim_config.get("filter_column")
    if not column or column not in df.columns:
        # Try to find column in specs_dict
        logger.debug(f"Column {column} not found, dimension {dimension} filter skipped")
        return df
    
    # Handle gearing/speed specially - need to parse to int
    if dimension == "gearing":
        parsed_value = _parse_gearing_value(value)
        if parsed_value is None:
            return df
        # Compare with speed column
        return df[df[column] == parsed_value]
    
    # For other dimensions
    if strategy == "strict":
        # Exact match (case-insensitive for strings)
        if isinstance(value, str):
            return df[df[column].fillna("").str.lower() == value.lower()]
        return df[df[column] == value]
    else:  # fuzzy
        # Substring match (case-insensitive)
        if isinstance(value, str):
            return df[df[column].fillna("").str.contains(value, case=False, na=False)]
        return df[df[column] == value]


def select_candidates_dynamic(
    categories: List[str],
    fit_values: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
    """Dynamically select product candidates for multiple categories.
    
    Queries database directly for memory efficiency instead of filtering
    an in-memory DataFrame.
    
    Args:
        categories: List of category keys to select products for.
        fit_values: Dict of known fit dimension values.
        
    Returns:
        Dict mapping category key to list of product dicts.
    """
    
    results: Dict[str, List[Dict[str, Any]]] = {}
    
    for cat in categories:
        cat_config = get_category_config(cat)
        if not cat_config:
            logger.warning(f"Unknown category: {cat}")
            continue
        
        # Query products for this category from database
        filtered = query_products(categories=[cat])
        
        if filtered.empty:
            logger.info(f"No products found for category: {cat}")
            results[cat] = []
            continue
        
        # Apply filters for each relevant fit dimension
        strategy = cat_config.get("filter_strategy", "strict")
        
        for dim in cat_config.get("fit_dimensions", []):
            if dim in fit_values and fit_values.get(dim) is not None:
                before_count = len(filtered)
                filtered = apply_fit_filter(filtered, dim, fit_values[dim], strategy)
                logger.debug(
                    f"Filter {dim}={fit_values[dim]} on {cat}: {before_count} -> {len(filtered)}"
                )
        
        # If filtering removed everything, try with just required dimensions
        if filtered.empty:
            logger.info(f"Filtering removed all products for {cat}, trying required only")
            filtered = query_products(categories=[cat])
            for dim in cat_config.get("required_fit", []):
                if dim in fit_values and fit_values.get(dim) is not None:
                    filtered = apply_fit_filter(filtered, dim, fit_values[dim], strategy)
        
        # Limit results
        max_results = cat_config.get("max_results", 5)
        filtered = filtered.head(max_results)
        
        # Convert to list of dicts
        results[cat] = [
            prepare_product_for_response(row)
            for _, row in filtered.iterrows()
        ]
        
        logger.info(f"Selected {len(results[cat])} candidates for {cat}")
    
    return results


def prepare_product_for_response(row: pd.Series) -> Dict[str, Any]:
    """Convert a DataFrame row to a product dict for API response.
    
    Args:
        row: DataFrame row representing a product.
        
    Returns:
        Dict with standardized product fields.
    """
    return {
        "name": _clean_value(row.get("name")),
        "url": _clean_value(row.get("url")),
        "brand": _clean_value(row.get("brand")),
        "price": _clean_value(row.get("price_text")),
        "application": _clean_value(row.get("application")),
        "speed": _clean_value(row.get("speed")),
        "specs": row.get("specs_dict", {}),
        "image_url": _normalize_image_url(row.get("image_url")),
    }


def get_available_categories_from_catalog(df: pd.DataFrame) -> List[str]:
    """Get list of categories that have products in the catalog.
    
    Useful for validating job identification results against actual data.
    
    Args:
        df: Product catalog DataFrame.
        
    Returns:
        List of category keys with at least one product.
    """
    if "category" not in df.columns:
        return []
    return df["category"].dropna().unique().tolist()


def validate_categories_against_catalog(
    categories: List[str],
    df: pd.DataFrame,
) -> List[str]:
    """Filter categories to only those with products in catalog.
    
    Args:
        categories: Requested categories.
        df: Product catalog DataFrame.
        
    Returns:
        List of categories that have products available.
    """
    available = set(get_available_categories_from_catalog(df))
    valid = [c for c in categories if c in available]
    
    if len(valid) < len(categories):
        missing = set(categories) - set(valid)
        logger.warning(f"Categories without products: {missing}")
    
    return valid
