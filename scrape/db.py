"""SQLite database schema and helpers for the scraper."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Set, Mapping

__all__ = [
    "DEFAULT_DB_PATH",
    "get_connection",
    "init_db",
    "get_existing_urls",
    "upsert_product",
    "add_product_category",
    "get_product_categories",
    "get_products_by_category",
    "upsert_dynamic_specs",
    "get_dynamic_specs",
    "save_discovered_fields",
    "get_discovered_fields",
    "get_all_discovered_fields",
    "update_scrape_state",
    "get_scrape_state",
    "get_all_products",
    "get_spec_table_for_category",
    "get_product_count",
]

# Default database path
DEFAULT_DB_PATH = "data/products.db"


def _get_valid_spec_tables() -> frozenset:
    """Generate whitelist of valid spec tables from CATEGORY_SPECS registry.

    This provides SQL injection prevention by validating table names against
    the known spec tables defined in the configuration.
    
    Called dynamically to support adding new categories without restart.
    """
    from scrape.config import CATEGORY_SPECS

    tables = set()
    for spec_config in CATEGORY_SPECS.values():
        if "spec_table" in spec_config:
            tables.add(spec_config["spec_table"])
    return frozenset(tables)


@contextmanager
def get_connection(db_path: str = DEFAULT_DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database connections."""
    # Ensure directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize the database schema."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Core products table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                image_url TEXT,
                brand TEXT,
                price_text TEXT,
                sku TEXT,
                breadcrumbs TEXT,
                description TEXT,
                specs_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Chain-specific specs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chain_specs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER UNIQUE NOT NULL,
                application TEXT,
                gearing TEXT,
                num_links TEXT,
                closure_type TEXT,
                pin_type TEXT,
                directional TEXT,
                material TEXT,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        """)

        # Cassette-specific specs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cassette_specs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER UNIQUE NOT NULL,
                application TEXT,
                gearing TEXT,
                gradation TEXT,
                sprocket_material TEXT,
                freehub_compatibility TEXT,
                recommended_chain TEXT,
                series TEXT,
                shifter TEXT,
                ebike TEXT,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        """)

        # Glove-specific specs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS glove_specs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER UNIQUE NOT NULL,
                size TEXT,
                material TEXT,
                padding TEXT,
                closure TEXT,
                touchscreen TEXT,
                season TEXT,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        """)

        # Tool-specific specs (shared by tool categories)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tool_specs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER UNIQUE NOT NULL,
                tool_type TEXT,
                compatibility TEXT,
                material TEXT,
                weight TEXT,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        """)

        # Product-Category junction table (many-to-many)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_categories (
                product_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                PRIMARY KEY (product_id, category),
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        """)

        # Pagination state tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scrape_state (
                category TEXT PRIMARY KEY,
                last_page_scraped INTEGER DEFAULT 0,
                last_scraped_at TIMESTAMP,
                total_pages_found INTEGER
            )
        """)

        # Dynamic specs table - stores normalized specs for ANY category
        # This replaces hardcoded per-category spec tables for new categories
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dynamic_specs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                field_name TEXT NOT NULL,
                field_value TEXT,
                UNIQUE(product_id, field_name),
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        """)

        # Discovered fields table - stores field discovery results per category
        # Used to know which fields to normalize during scraping
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discovered_fields (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                field_name TEXT NOT NULL,
                original_labels TEXT NOT NULL,
                frequency REAL NOT NULL,
                sample_values TEXT,
                discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(category, field_name)
            )
        """)

        # Indexes for common queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_url ON products(url)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_categories_category ON product_categories(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_categories_product_id ON product_categories(product_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dynamic_specs_product ON dynamic_specs(product_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dynamic_specs_category ON dynamic_specs(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dynamic_specs_field ON dynamic_specs(field_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_discovered_fields_category ON discovered_fields(category)")

        conn.commit()


def get_existing_urls(db_path: str = DEFAULT_DB_PATH, category: Optional[str] = None) -> Set[str]:
    """Get all existing product URLs, optionally filtered by category."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if category:
            cursor.execute("SELECT url FROM products WHERE category = ?", (category,))
        else:
            cursor.execute("SELECT url FROM products")
        return {row["url"] for row in cursor.fetchall()}


def upsert_product(
    db_path: str,
    category: str,
    name: str,
    url: str,
    image_url: Optional[str] = None,
    brand: Optional[str] = None,
    price_text: Optional[str] = None,
    sku: Optional[str] = None,
    breadcrumbs: Optional[str] = None,
    description: Optional[str] = None,
    specs: Optional[Dict[str, str]] = None,
) -> int:
    """Insert or update a product, returning its ID."""
    specs_json = json.dumps(specs, ensure_ascii=False) if specs else None

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Check if product exists
        cursor.execute("SELECT id FROM products WHERE url = ?", (url,))
        existing = cursor.fetchone()

        if existing:
            # Update existing
            cursor.execute("""
                UPDATE products SET
                    category = ?,
                    name = ?,
                    image_url = ?,
                    brand = ?,
                    price_text = ?,
                    sku = ?,
                    breadcrumbs = ?,
                    description = ?,
                    specs_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE url = ?
            """, (category, name, image_url, brand, price_text, sku,
                  breadcrumbs, description, specs_json, url))
            product_id = existing["id"]
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO products (category, name, url, image_url, brand, price_text,
                                     sku, breadcrumbs, description, specs_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (category, name, url, image_url, brand, price_text, sku,
                  breadcrumbs, description, specs_json))
            product_id = cursor.lastrowid

        conn.commit()
        return product_id


def update_scrape_state(
    db_path: str,
    category: str,
    last_page: int,
    total_pages: Optional[int] = None,
) -> None:
    """Update the pagination state for a category."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO scrape_state (category, last_page_scraped, last_scraped_at, total_pages_found)
            VALUES (?, ?, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(category) DO UPDATE SET
                last_page_scraped = ?,
                last_scraped_at = CURRENT_TIMESTAMP,
                total_pages_found = COALESCE(?, total_pages_found)
        """, (category, last_page, total_pages, last_page, total_pages))
        conn.commit()


def get_scrape_state(db_path: str, category: str) -> Optional[Dict[str, Any]]:
    """Get the pagination state for a category."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT last_page_scraped, total_pages_found, last_scraped_at FROM scrape_state WHERE category = ?",
            (category,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "last_page_scraped": row["last_page_scraped"],
                "total_pages_found": row["total_pages_found"],
                "last_scraped_at": row["last_scraped_at"],
            }
        return None


def get_all_products(
    db_path: str = DEFAULT_DB_PATH,
    category: Optional[str] = None,
    include_specs: bool = True,
) -> List[Dict[str, Any]]:
    """Retrieve all products, optionally with their category-specific specs."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        if category:
            cursor.execute("SELECT * FROM products WHERE category = ?", (category,))
        else:
            cursor.execute("SELECT * FROM products")

        products = []
        for row in cursor.fetchall():
            product = dict(row)
            # Parse specs_json back to dict
            if product.get("specs_json"):
                product["specs"] = json.loads(product["specs_json"])
            del product["specs_json"]


            products.append(product)

        return products


def get_spec_table_for_category(category: str) -> Optional[str]:
    """Map category to its spec table name.
    
    Uses CATEGORY_SPECS registry from config.py as single source of truth.
    """
    from scrape.config import get_spec_config

    spec_config = get_spec_config(category)
    return spec_config.get("spec_table") if spec_config else None


def get_product_count(db_path: str = DEFAULT_DB_PATH, category: Optional[str] = None) -> int:
    """Get the total number of products.
    
    Args:
        db_path: Path to database.
        category: Optional category filter. Uses junction table if available.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if category:
            # Try junction table first, fall back to single category field
            cursor.execute("""
                SELECT COUNT(DISTINCT p.id) as count 
                FROM products p
                LEFT JOIN product_categories pc ON p.id = pc.product_id
                WHERE pc.category = ? OR p.category = ?
            """, (category, category))
        else:
            cursor.execute("SELECT COUNT(*) as count FROM products")
        return cursor.fetchone()["count"]


def add_product_category(
    db_path: str,
    product_id: int,
    category: str,
) -> None:
    """Add a category association for a product.
    
    Idempotent - will not fail if association already exists.
    
    Args:
        db_path: Path to database.
        product_id: ID of the product.
        category: Category to associate with the product.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO product_categories (product_id, category)
            VALUES (?, ?)
        """, (product_id, category))
        conn.commit()


def get_product_categories(db_path: str, product_id: int) -> List[str]:
    """Get all categories associated with a product.
    
    Args:
        db_path: Path to database.
        product_id: ID of the product.
        
    Returns:
        List of category strings.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT category FROM product_categories
            WHERE product_id = ?
            ORDER BY category
        """, (product_id,))
        return [row["category"] for row in cursor.fetchall()]


def get_products_by_category(
    db_path: str,
    category: str,
    include_specs: bool = True,
) -> List[Dict[str, Any]]:
    """Get all products associated with a category via junction table.
    
    Args:
        db_path: Path to database.
        category: Category to filter by.
        include_specs: Whether to include category-specific specs.
        
    Returns:
        List of product dictionaries.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Get products through junction table
        cursor.execute("""
            SELECT DISTINCT p.*
            FROM products p
            JOIN product_categories pc ON p.id = pc.product_id
            WHERE pc.category = ?
            ORDER BY p.name
        """, (category,))
        
        rows = cursor.fetchall()
        products = []
        
        for row in rows:
            product = dict(row)
            
            # Parse specs JSON
            if product.get("specs_json"):
                try:
                    product["specs"] = json.loads(product["specs_json"])
                except json.JSONDecodeError:
                    product["specs"] = {}
            else:
                product["specs"] = {}
            
            del product["specs_json"]
            

            products.append(product)
        
        return products


# =============================================================================
# Dynamic Specs Functions (new flexible system)
# =============================================================================

def upsert_dynamic_specs(
    db_path: str,
    product_id: int,
    category: str,
    specs: Mapping[str, Optional[str]],
) -> None:
    """Insert or update dynamic specs for a product.
    
    This stores specs in the flexible dynamic_specs table, allowing any
    category to have normalized specs without needing a dedicated table.
    
    Args:
        db_path: Path to database.
        product_id: ID of the product.
        category: Category key for the product.
        specs: Dict of {field_name: field_value} to store. None values are skipped.
    """
    if not specs:
        return
    
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        for field_name, field_value in specs.items():
            # Skip None values - these occur when a field mapping doesn't find a match
            if field_value is None:
                continue
            
            cursor.execute("""
                INSERT INTO dynamic_specs (product_id, category, field_name, field_value)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(product_id, field_name) DO UPDATE SET
                    field_value = excluded.field_value,
                    category = excluded.category
            """, (product_id, category, field_name, field_value))
        
        conn.commit()


def get_dynamic_specs(db_path: str, product_id: int) -> Dict[str, str]:
    """Get dynamic specs for a product.
    
    Args:
        db_path: Path to database.
        product_id: ID of the product.
        
    Returns:
        Dict of {field_name: field_value}.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT field_name, field_value
            FROM dynamic_specs
            WHERE product_id = ?
        """, (product_id,))
        
        return {row["field_name"]: row["field_value"] for row in cursor.fetchall()}


def get_all_dynamic_specs_for_category(db_path: str, category: str) -> Dict[int, Dict[str, str]]:
    """Get all dynamic specs for products in a category.
    
    Args:
        db_path: Path to database.
        category: Category to filter by.
        
    Returns:
        Dict of {product_id: {field_name: field_value}}.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT product_id, field_name, field_value
            FROM dynamic_specs
            WHERE category = ?
        """, (category,))
        
        result: Dict[int, Dict[str, str]] = {}
        for row in cursor.fetchall():
            pid = row["product_id"]
            if pid not in result:
                result[pid] = {}
            result[pid][row["field_name"]] = row["field_value"]
        
        return result


# =============================================================================
# Discovered Fields Functions
# =============================================================================

def save_discovered_fields(
    db_path: str,
    category: str,
    fields: List[Dict[str, Any]],
) -> None:
    """Save discovered fields for a category.
    
    Replaces any existing discovered fields for the category.
    
    Args:
        db_path: Path to database.
        category: Category key.
        fields: List of field dicts with keys:
            - field_name: normalized column name
            - original_labels: list of original HTML labels that map to this field
            - frequency: how often this field appears (0-1)
            - sample_values: example values (optional)
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Clear existing fields for this category
        cursor.execute("DELETE FROM discovered_fields WHERE category = ?", (category,))
        
        # Insert new fields
        for field in fields:
            labels_json = json.dumps(field.get("original_labels", [field.get("label", field["field_name"])]))
            samples_json = json.dumps(field.get("sample_values", []))
            
            cursor.execute("""
                INSERT INTO discovered_fields (category, field_name, original_labels, frequency, sample_values)
                VALUES (?, ?, ?, ?, ?)
            """, (
                category,
                field["field_name"],
                labels_json,
                field.get("frequency", 1.0),
                samples_json,
            ))
        
        conn.commit()


def get_discovered_fields(db_path: str, category: str) -> List[Dict[str, Any]]:
    """Get discovered fields for a category.
    
    Args:
        db_path: Path to database.
        category: Category key.
        
    Returns:
        List of field dicts with field_name, original_labels, frequency, sample_values.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT field_name, original_labels, frequency, sample_values, discovered_at
            FROM discovered_fields
            WHERE category = ?
            ORDER BY frequency DESC
        """, (category,))
        
        fields = []
        for row in cursor.fetchall():
            fields.append({
                "field_name": row["field_name"],
                "original_labels": json.loads(row["original_labels"]),
                "frequency": row["frequency"],
                "sample_values": json.loads(row["sample_values"]) if row["sample_values"] else [],
                "discovered_at": row["discovered_at"],
            })
        
        return fields


def get_all_discovered_fields(db_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """Get all discovered fields grouped by category.
    
    Args:
        db_path: Path to database.
        
    Returns:
        Dict of {category: [field_dicts]}.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT category, field_name, original_labels, frequency, sample_values
            FROM discovered_fields
            ORDER BY category, frequency DESC
        """)
        
        result: Dict[str, List[Dict[str, Any]]] = {}
        for row in cursor.fetchall():
            cat = row["category"]
            if cat not in result:
                result[cat] = []
            result[cat].append({
                "field_name": row["field_name"],
                "original_labels": json.loads(row["original_labels"]),
                "frequency": row["frequency"],
                "sample_values": json.loads(row["sample_values"]) if row["sample_values"] else [],
            })
        
        return result


def get_dynamic_spec_fields_for_category(db_path: str, category: str) -> List[str]:
    """Get list of unique field names in dynamic_specs for a category.
    
    Args:
        db_path: Path to database.
        category: Category to query.
        
    Returns:
        List of unique field names.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT field_name
            FROM dynamic_specs
            WHERE category = ?
            ORDER BY field_name
        """, (category,))
        
        return [row["field_name"] for row in cursor.fetchall()]
