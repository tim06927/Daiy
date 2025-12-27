"""SQLite database schema and helpers for the scraper."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Set

__all__ = [
    "DEFAULT_DB_PATH",
    "get_connection",
    "init_db",
    "get_existing_urls",
    "upsert_product",
    "upsert_category_specs",
    "update_scrape_state",
    "get_scrape_state",
    "get_all_products",
    "get_spec_table_for_category",
    "get_product_count",
]

# Default database path
DEFAULT_DB_PATH = "data/products.db"


def _get_valid_spec_tables() -> set:
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
    return tables


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

        # Tool-specific specs (for drivetrain_tools, shifters_derailleurs)
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

        # Pagination state tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scrape_state (
                category TEXT PRIMARY KEY,
                last_page_scraped INTEGER DEFAULT 0,
                last_scraped_at TIMESTAMP,
                total_pages_found INTEGER
            )
        """)

        # Indexes for common queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_url ON products(url)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku)")

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


def upsert_category_specs(
    db_path: str,
    table_name: str,
    product_id: int,
    specs: Dict[str, Any],
) -> None:
    """Insert or update category-specific specs."""
    if not specs:
        return

    # Validate table name against whitelist to prevent SQL injection
    valid_tables = _get_valid_spec_tables()
    if table_name not in valid_tables:
        raise ValueError(f"Invalid table name: {table_name}. Must be one of {valid_tables}")

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Get column names for the table (excluding id and product_id)
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row["name"] for row in cursor.fetchall()
                   if row["name"] not in ("id", "product_id")]

        # Filter specs to only include valid columns
        valid_specs = {k: v for k, v in specs.items() if k in columns}
        if not valid_specs:
            return

        # Check if exists
        cursor.execute(f"SELECT id FROM {table_name} WHERE product_id = ?", (product_id,))
        existing = cursor.fetchone()

        if existing:
            # Update
            set_clause = ", ".join(f"{k} = ?" for k in valid_specs.keys())
            values = list(valid_specs.values()) + [product_id]
            cursor.execute(f"UPDATE {table_name} SET {set_clause} WHERE product_id = ?", values)
        else:
            # Insert
            cols = ["product_id"] + list(valid_specs.keys())
            placeholders = ", ".join("?" for _ in cols)
            col_names = ", ".join(cols)
            values = [product_id] + list(valid_specs.values())
            cursor.execute(f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})", values)

        conn.commit()


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

            if include_specs:
                # Get category-specific specs
                spec_table = get_spec_table_for_category(product["category"])
                if spec_table:
                    # Validate table name against whitelist to prevent SQL injection
                    valid_tables = _get_valid_spec_tables()
                    if spec_table not in valid_tables:
                        raise ValueError(f"Invalid table name: {spec_table}. Must be one of {valid_tables}")

                    cursor.execute(
                        f"SELECT * FROM {spec_table} WHERE product_id = ?",
                        (product["id"],)
                    )
                    spec_row = cursor.fetchone()
                    if spec_row:
                        spec_dict = dict(spec_row)
                        del spec_dict["id"]
                        del spec_dict["product_id"]
                        product["category_specs"] = spec_dict

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
    """Get the total number of products."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if category:
            cursor.execute("SELECT COUNT(*) as count FROM products WHERE category = ?", (category,))
        else:
            cursor.execute("SELECT COUNT(*) as count FROM products")
        return cursor.fetchone()["count"]
