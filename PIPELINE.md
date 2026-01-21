# Scraper to Web App Pipeline

## Overview

The scraper and web app share the same SQLite database (`data/products.db`), enabling automatic product availability in the web app as soon as the scraper adds them.

```
┌──────────────┐
│   Scraper    │  writes products
│ (scrape/cli) │ ────────────┐
└──────────────┘             │
                             ▼
                    ┌─────────────────┐
                    │ products.db     │
                    │ (SQLite)        │
                    └─────────────────┘
                             ▲
                             │ queries on-demand
┌──────────────┐             │
│   Web App    │ ────────────┘
│  (web/api)   │  reads products
└──────────────┘
```

## Pipeline Flow

### 1. Scraper Writes to Database

```python
# scrape/db.py - upsert_product()
from scrape.db import upsert_product, get_connection

# Scraper adds/updates products
product_id = upsert_product(
    category="drivetrain_cassettes",
    name="Shimano XT CS-M8000",
    url="https://...",
    # ... other fields
    specs_json='{"Gearing": "11", "Application": "MTB"}'
)
```

### 2. Web App Reads from Database

```python
# web/catalog.py - query_products()
from catalog import query_products

# Web app immediately sees new products (no restart needed)
products = query_products(categories=['drivetrain_cassettes'])
```

### 3. Categories Auto-Refresh

When the scraper adds products to a new category, the web app automatically discovers it:

```python
# web/categories.py - discover_categories_from_catalog()
from catalog import get_categories

# Returns all categories including newly scraped ones
categories = get_categories()  # Queries: SELECT DISTINCT category FROM products
```

## Schema Compatibility

### Current Setup (CSV-based Database)

The database created from CSV export has this schema:
- Column: `specs` (TEXT) - JSON string with product specifications
- Created by: `pandas.to_sql()` from CSV

### Scraper Schema

The scraper's native schema uses:
- Column: `specs_json` (TEXT) - JSON string with product specifications
- Created by: `scrape/db.py - init_db()`

### Compatibility Layer

The web app (`web/catalog.py`) handles both column names automatically:

```python
def _add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Handles both 'specs' (CSV) and 'specs_json' (scraper) columns."""
    specs_col = "specs_json" if "specs_json" in df.columns else "specs"
    df["specs_dict"] = df[specs_col].apply(_parse_specs)
    # ...
```

## Testing the Pipeline

Test that products scraped → immediately available in web app:

```bash
# 1. Run scraper to add products
python -m scrape.cli --max-pages 1

# 2. Check web app sees them (no restart needed)
python -c "
from catalog import get_product_count
print(f'Products available: {get_product_count()}')
"

# 3. Start web app and verify in UI
python web/app.py
# Visit http://localhost:5000
```

## Migration Path

### Option A: Keep CSV-based Database (Current)
- ✅ Works with existing scraper
- ✅ Web app handles both schemas
- ✅ No migration needed

### Option B: Recreate with Scraper Schema
If you want to use the scraper's native schema:

```bash
# 1. Initialize database with scraper schema
python -c "
from scrape.db import init_db
init_db('data/products.db')
"

# 2. Run scraper to populate
python -m scrape.cli --mode full

# 3. Web app will work with both schemas
```

## Real-Time Updates

**No restart required!** When the scraper adds products:

1. Scraper writes to `data/products.db`
2. Web app's next query sees new products immediately
3. Categories refresh on next request
4. Product selection picks up new items

**Example:**
```bash
# Terminal 1: Web app running
python web/app.py

# Terminal 2: Scraper adds 100 new products
python -m scrape.cli --category drivetrain_chains --max-pages 5

# Terminal 1: Web app immediately sees new products
# No restart needed! Next API request includes them.
```

## Troubleshooting

### Products not appearing in web app?

**Check database path:**
```python
# Both should be 'data/products.db'
from scrape.db import DEFAULT_DB_PATH as SCRAPE_DB
from catalog import DEFAULT_DB_PATH as WEB_DB
print(f'Scraper: {SCRAPE_DB}')
print(f'Web app: {WEB_DB}')
```

**Check product count:**
```bash
sqlite3 data/products.db "SELECT COUNT(*) FROM products"
```

**Check if web app can query:**
```python
from catalog import get_product_count
print(get_product_count())  # Should match database count
```

### Schema mismatch errors?

The web app handles both schemas automatically. If you see errors:

1. Check which column exists:
```bash
sqlite3 data/products.db ".schema products" | grep -E "specs|specs_json"
```

2. Verify compatibility layer is working:
```python
from catalog import query_products
df = query_products(limit=1)
print('specs_dict' in df.columns)  # Should be True
```

## Performance

- **Database size**: 45.6 MB for 11k products
- **Query speed**: <100ms for category queries (indexed)
- **Memory usage**: 0.2-5MB per query (vs 500MB loading full CSV)
- **Startup time**: Instant (no data loading)

## Summary

✅ **Pipeline Status: WORKING**
- Scraper and web app share `data/products.db`
- Products added by scraper appear immediately in web app
- No restart or migration needed
- Both CSV and scraper schemas supported
- Real-time updates without downtime
