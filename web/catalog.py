"""Database-backed catalog using the scraper's SQLite database.

This module provides memory-efficient product queries by directly using
the SQLite database created by the scraper. No CSV loading required!

Memory usage: <50MB (queries on-demand) vs 500MB+ (loading full CSV).
"""

import json
import os
import re
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

# Handle imports for both direct execution and package import
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).parent))
else:
    pass

__all__ = ["get_catalog", "query_products", "get_categories", "get_product_count"]

# Use the same database as the scraper
DEFAULT_DB_PATH = "data/products.db"


@contextmanager
def _get_db_connection(db_path: str = DEFAULT_DB_PATH):
    """Get SQLite database connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _parse_specs(specs_json: Optional[str]) -> Dict[str, Any]:
    """Parse specs_json or specs field from database.
    
    Handles both column names for compatibility:
    - specs_json (scraper schema)
    - specs (CSV export schema)
    """
    if not specs_json or pd.isna(specs_json):
        return {}
    try:
        result = json.loads(specs_json)
        return dict(result) if isinstance(result, dict) else {}
    except:
        return {}


def _derive_speed(specs_dict: Dict, name: str) -> Optional[int]:
    """Derive speed from specs or product name."""
    # Try specs Gearing
    g = specs_dict.get("Gearing")
    if isinstance(g, str):
        m = re.search(r"\d+", g)
        if m:
            return int(m.group())
    
    # Fallback: extract from name
    if name:
        m = re.search(r"(\d{1,2})[\-\s]?(?:speed|s(?:pd)?)\b", name, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None


def _derive_application(specs_dict: Dict, name: str) -> Optional[str]:
    """Derive application from specs or product name."""
    app = specs_dict.get("Application")
    if isinstance(app, str):
        return app
    
    # Fallback: extract from name
    if name:
        name_lower = name.lower()
        for keyword in ["road", "gravel", "mtb", "mountain", "e-bike", "ebike", "touring"]:
            if keyword in name_lower:
                return keyword.title()
    return None


def query_products(
    categories: Optional[List[str]] = None,
    filters: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> pd.DataFrame:
    """Query products from database with optional filters.
    
    This is the main query function that should be used instead of loading
    the full catalog into memory.
    
    Args:
        categories: Filter by category list (OR condition).
        filters: Additional column filters (exact match).
        limit: Maximum number of results.
        db_path: Path to SQLite database.
        
    Returns:
        DataFrame with matching products (includes derived columns).
    """
    # Build SQL query
    query = "SELECT * FROM products WHERE 1=1"
    params = []
    
    if categories:
        # Support both exact category match and multi-category products
        placeholders = ','.join(['?' for _ in categories])
        query += f" AND category IN ({placeholders})"
        params.extend(categories)
    
    if filters:
        for col, val in filters.items():
            # Sanitize column name
            if not col.replace('_', '').isalnum():
                continue
            
            if val is None:
                query += f" AND {col} IS NULL"
            else:
                query += f" AND {col} = ?"
                params.append(val)
    
    if limit:
        query += f" LIMIT {int(limit)}"
    
    # Execute query
    with _get_db_connection(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=params)
    
    # Add derived columns
    if not df.empty:
        df = _add_derived_columns(df)
    
    return df


def _add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived columns (specs_dict, speed, application) to query results."""
    # Parse specs JSON - handle both column names for compatibility
    specs_col = None
    if "specs_json" in df.columns:
        specs_col = "specs_json"
    elif "specs" in df.columns:
        specs_col = "specs"
    
    if specs_col:
        df["specs_dict"] = df[specs_col].apply(_parse_specs)
    else:
        df["specs_dict"] = [{} for _ in range(len(df))]
    
    # Derive speed and application
    df["speed"] = df.apply(
        lambda row: _derive_speed(row["specs_dict"], row.get("name", "")),
        axis=1
    )
    df["application"] = df.apply(
        lambda row: _derive_application(row["specs_dict"], row.get("name", "")),
        axis=1
    )
    
    return df


def get_categories(db_path: str = DEFAULT_DB_PATH) -> List[str]:
    """Get list of all available product categories.
    
    Args:
        db_path: Path to SQLite database.
        
    Returns:
        List of unique category names.
    """
    query = "SELECT DISTINCT category FROM products WHERE category IS NOT NULL ORDER BY category"
    
    with _get_db_connection(db_path) as conn:
        df = pd.read_sql_query(query, conn)
    
    return df['category'].tolist()


def get_product_count(
    categories: Optional[List[str]] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> int:
    """Count products matching criteria.
    
    Args:
        categories: Filter by category list.
        db_path: Path to SQLite database.
        
    Returns:
        Number of matching products.
    """
    query = "SELECT COUNT(*) as count FROM products WHERE 1=1"
    params = []
    
    if categories:
        placeholders = ','.join(['?' for _ in categories])
        query += f" AND category IN ({placeholders})"
        params.extend(categories)
    
    with _get_db_connection(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=params)
    
    return int(df['count'].iloc[0])


# Backward compatibility function
def get_catalog(db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Get all products from catalog.
    
    WARNING: This loads all data into memory. Use query_products() instead!
    This function is only for backward compatibility.
    
    Args:
        db_path: Path to SQLite database.
        
    Returns:
        DataFrame with all products.
    """
    return query_products(db_path=db_path)
