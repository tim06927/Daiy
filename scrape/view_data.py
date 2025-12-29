#!/usr/bin/env python3
"""View scraped data and category discovery results in HTML format.

Usage:
    python -m scrape.view_data                                # View all data
    python -m scrape.view_data --open                         # Auto-open in browser
    python -m scrape.view_data --output PATH                  # Write HTML to PATH
    python -m scrape.view_data --db PATH                      # Use alternative SQLite DB
    python -m scrape.view_data --categories-json PATH         # Use alternative categories JSON
"""

import argparse
import json
import sqlite3
import webbrowser
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = [
    "regenerate_report",
    "get_db_stats",
    "get_scrape_state",
    "get_data_quality",
    "load_discovered_categories",
    "compute_category_coverage",
]

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "products.db"
CATEGORIES_JSON = DATA_DIR / "discovered_categories.json"
OUTPUT_HTML = DATA_DIR / "scrape_data_view.html"


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


# =============================================================================
# Database Queries
# =============================================================================

def get_db_stats(db_path: Path) -> Dict[str, Any]:
    """Get overall database statistics."""
    if not db_path.exists():
        return {"exists": False}
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        stats = {"exists": True}
        
        # Total products
        cursor.execute("SELECT COUNT(*) as count FROM products")
        stats["total_products"] = cursor.fetchone()["count"]
        
        # Products by category
        cursor.execute("""
            SELECT category, COUNT(*) as count 
            FROM products 
            GROUP BY category 
            ORDER BY count DESC
        """)
        stats["by_category"] = {row["category"]: row["count"] for row in cursor.fetchall()}
        
        # Products by brand (top 20)
        cursor.execute("""
            SELECT brand, COUNT(*) as count 
            FROM products 
            WHERE brand IS NOT NULL AND brand != ''
            GROUP BY brand 
            ORDER BY count DESC 
            LIMIT 20
        """)
        stats["top_brands"] = [(row["brand"], row["count"]) for row in cursor.fetchall()]
        
        # Date range
        cursor.execute("SELECT MIN(created_at) as first, MAX(updated_at) as last FROM products")
        row = cursor.fetchone()
        stats["first_scraped"] = row["first"]
        stats["last_updated"] = row["last"]
        
        # Get all unique URLs from products for coverage matching
        cursor.execute("SELECT DISTINCT url FROM products")
        stats["scraped_urls"] = {row["url"] for row in cursor.fetchall()}
    
    return stats


def get_scrape_state(db_path: Path) -> List[Dict[str, Any]]:
    """Get scrape state for all categories."""
    if not db_path.exists():
        return []
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT category, last_page_scraped, last_scraped_at, total_pages_found
            FROM scrape_state
            ORDER BY category
        """)
        
        states = [dict(row) for row in cursor.fetchall()]
    
    return states


def get_data_quality(db_path: Path) -> Dict[str, Any]:
    """Analyze data quality issues."""
    if not db_path.exists():
        return {}
    
    # Allowlist of valid field and table names to prevent SQL injection
    VALID_FIELDS = ["name", "url", "brand", "price_text", "sku", "description", "image_url"]
    VALID_SPEC_TABLES = ["chain_specs", "cassette_specs", "glove_specs", "tool_specs"]
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        quality = {}
        
        # Missing fields analysis
        missing = {}
        for field in VALID_FIELDS:
            cursor.execute(f"SELECT COUNT(*) as count FROM products WHERE {field} IS NULL OR {field} = ''")
            missing[field] = cursor.fetchone()["count"]
        quality["missing_fields"] = missing
        
        # Duplicate URLs
        cursor.execute("""
            SELECT url, COUNT(*) as count 
            FROM products 
            GROUP BY url 
            HAVING count > 1
        """)
        quality["duplicate_urls"] = cursor.fetchall()
        
        # Products without specs
        cursor.execute("SELECT COUNT(*) as count FROM products WHERE specs_json IS NULL OR specs_json = ''")
        quality["missing_specs"] = cursor.fetchone()["count"]
        
        # Category spec coverage
        spec_coverage = {}
        for table in VALID_SPEC_TABLES:
            try:
                cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                spec_coverage[table] = cursor.fetchone()["count"]
            except sqlite3.OperationalError:
                spec_coverage[table] = 0
        quality["spec_table_counts"] = spec_coverage
    
    return quality


def get_sample_products(db_path: Path, category: Optional[str] = None, limit: int = 5) -> List[Dict]:
    """Get sample products for preview."""
    if not db_path.exists():
        return []
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if category:
            cursor.execute("""
                SELECT id, category, name, brand, price_text, url, sku
                FROM products 
                WHERE category = ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (category, limit))
        else:
            cursor.execute("""
                SELECT id, category, name, brand, price_text, url, sku
                FROM products 
                ORDER BY updated_at DESC
                LIMIT ?
            """, (limit,))
        
        products = [dict(row) for row in cursor.fetchall()]
    
    return products


def compute_category_coverage(category_data: Dict, db_stats: Dict) -> Dict[str, Any]:
    """Compute which discovered categories have been scraped.
    
    Returns coverage analysis comparing discovered categories with scraped data.
    """
    if not category_data.get("exists"):
        return {"exists": False}
    
    categories = category_data.get("categories", [])
    leaf_categories = category_data.get("leaf_categories", [])
    
    # Match discovered category URLs to scraped product URLs
    # A category is "scraped" if we have products from its URL path
    coverage = {
        "total_discovered": len(categories),
        "total_leaf": len(leaf_categories),
        "scraped_categories": [],
        "not_scraped_categories": [],
        "partial_match": [],  # Categories that match a scraped category key
    }
    
    for cat in leaf_categories:
        cat_url = cat.get("url", "")
        cat_key = cat.get("key", "")
        cat_path = cat.get("path", "")
        
        # Check if this category's key matches any scraped category
        is_scraped = False
        product_count = 0
        
        # Direct key match with exact match only to avoid false positives
        for scraped_key, count in db_stats.get("by_category", {}).items():
            # Use exact match only to prevent false positives like "chain" matching "chain-tool"
            if scraped_key == cat_key:
                is_scraped = True
                product_count = count
                break
        
        cat_info = {
            "key": cat_key,
            "name": cat.get("name", ""),
            "url": cat_url,
            "path": cat_path,
            "depth": cat.get("depth", 0),
            "segments": cat.get("segments", []),
            "product_count": product_count,
        }
        
        if is_scraped:
            coverage["scraped_categories"].append(cat_info)
        else:
            coverage["not_scraped_categories"].append(cat_info)
    
    coverage["scraped_count"] = len(coverage["scraped_categories"])
    coverage["not_scraped_count"] = len(coverage["not_scraped_categories"])
    coverage["coverage_pct"] = (
        (coverage["scraped_count"] / coverage["total_leaf"] * 100)
        if coverage["total_leaf"] > 0 else 0
    )
    coverage["exists"] = True
    
    return coverage


# =============================================================================
# Category Discovery Data
# =============================================================================

def load_discovered_categories(json_path: Path) -> Dict[str, Any]:
    """Load discovered categories from JSON file."""
    if not json_path.exists():
        return {"exists": False}
    
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        # Return a graceful error state instead of raising an unhandled exception
        return {"exists": False, "error": str(exc)}
    
    data["exists"] = True
    try:
        mtime = json_path.stat().st_mtime
    except OSError:
        mtime = None
    data["file_modified"] = (
        datetime.fromtimestamp(mtime).isoformat() if mtime is not None else None
    )
    return data


def build_category_tree_html(categories: List[Dict], max_depth: int = 4) -> str:
    """Build an HTML tree view of categories."""
    if not categories:
        return "<p>No categories discovered yet.</p>"
    
    # Group by top-level category
    by_top_level: Dict[str, List[Dict]] = defaultdict(list)
    for cat in categories:
        segments = cat.get("segments") or []
        if segments:
            by_top_level[segments[0]].append(cat)
    
    # Build nested structure
    html = ['<div class="category-tree">']
    
    for top_level in sorted(by_top_level.keys()):
        cats = by_top_level[top_level]
        # Compute max depth for categories under this top-level, handling missing segments safely
        top_level_cats = [
            cc for cc in cats
            if (cc.get("segments") or [None])[0] == top_level
        ]
        
        html.append(f'<details class="tree-section" open>')
        html.append(f'<summary><span class="folder-icon">📁</span> <strong>{escape_html(top_level.replace("-", " ").title())}</strong> <span class="count">({len(cats)} categories)</span></summary>')
        html.append('<ul class="tree-list">')
        
        # Build nested tree
        tree = _build_nested_tree(cats)
        html.append(_render_tree_html(tree, current_depth=1, max_depth=max_depth))
        
        html.append('</ul>')
        html.append('</details>')
    
    html.append('</div>')
    return "\n".join(html)


def _build_nested_tree(categories: List[Dict]) -> Dict:
    """Build a nested dictionary tree from flat category list."""
    tree: Dict = {}
    
    for cat in sorted(categories, key=lambda x: x.get("depth", 0)):
        segments = cat.get("segments", [])
        current = tree
        
        for i, segment in enumerate(segments):
            if segment not in current:
                current[segment] = {"_children": {}, "_meta": None}
            
            if i == len(segments) - 1:
                current[segment]["_meta"] = cat
            
            current = current[segment]["_children"]
    
    return tree


def _render_tree_html(tree: Dict, current_depth: int = 0, max_depth: int = 4) -> str:
    """Render tree as nested HTML lists."""
    if current_depth >= max_depth:
        remaining = len([k for k in tree.keys() if not k.startswith("_")])
        if remaining > 0:
            return f'<li class="more-items">... and {remaining} more subcategories</li>'
        return ""
    
    html_parts = []
    
    for key in sorted(tree.keys()):
        if key.startswith("_"):
            continue
        
        node = tree[key]
        meta = node.get("_meta", {})
        children = node.get("_children", {})
        child_count = len([k for k in children.keys() if not k.startswith("_")])
        
        name = meta.get("name", key.replace("-", " ").title()) if meta else key.replace("-", " ").title()
        url = meta.get("url", "") if meta else ""
        
        if child_count > 0:
            html_parts.append(f'<li class="has-children">')
            html_parts.append(f'<details><summary>')
            if url:
                html_parts.append(f'<a href="{escape_html(url)}" target="_blank" title="{escape_html(url)}">{escape_html(name)}</a>')
            else:
                html_parts.append(f'{escape_html(name)}')
            html_parts.append(f' <span class="count">({child_count})</span></summary>')
            html_parts.append('<ul>')
            html_parts.append(_render_tree_html(children, current_depth + 1, max_depth))
            html_parts.append('</ul></details></li>')
        else:
            html_parts.append(f'<li class="leaf">')
            if url:
                html_parts.append(f'<a href="{escape_html(url)}" target="_blank" title="{escape_html(url)}">{escape_html(name)}</a>')
            else:
                html_parts.append(f'{escape_html(name)}')
            html_parts.append('</li>')
    
    return "\n".join(html_parts)


# =============================================================================
# HTML Generation
# =============================================================================

def generate_html(
    db_stats: Dict[str, Any],
    scrape_states: List[Dict],
    quality: Dict[str, Any],
    sample_products: List[Dict],
    category_data: Dict[str, Any],
    coverage_data: Dict[str, Any],
) -> str:
    """Generate the full HTML report."""
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Build sections
    overview_html = _build_overview_section(db_stats, category_data, coverage_data)
    scrape_progress_html = _build_scrape_progress_section(scrape_states, db_stats)
    category_tree_html = _build_category_section(category_data)
    coverage_html = _build_coverage_section(coverage_data)
    quality_html = _build_quality_section(quality, db_stats)
    products_html = _build_products_section(sample_products, db_stats)
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Scrape Data Viewer</title>
    <style>
        :root {{
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --bg-card: #0f3460;
            --text-primary: #eaeaea;
            --text-secondary: #a0a0a0;
            --accent: #e94560;
            --accent-secondary: #0ea5e9;
            --success: #22c55e;
            --warning: #f59e0b;
            --error: #ef4444;
            --border: #334155;
        }}
        
        * {{ box-sizing: border-box; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid var(--border);
        }}
        
        header h1 {{
            color: var(--accent);
            margin: 0 0 10px 0;
            font-size: 2.5em;
        }}
        
        .timestamp {{
            color: var(--text-secondary);
            font-size: 0.9em;
        }}
        
        /* Navigation */
        .nav-tabs {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}
        
        .nav-tab {{
            padding: 10px 20px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text-primary);
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .nav-tab:hover, .nav-tab.active {{
            background: var(--accent);
            border-color: var(--accent);
        }}
        
        /* Sections */
        .section {{
            display: none;
            animation: fadeIn 0.3s ease;
        }}
        
        .section.active {{
            display: block;
        }}
        
        @keyframes fadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}
        
        /* Cards */
        .card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }}
        
        .card h2 {{
            color: var(--accent-secondary);
            margin: 0 0 15px 0;
            font-size: 1.4em;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .card h3 {{
            color: var(--text-primary);
            margin: 15px 0 10px 0;
            font-size: 1.1em;
        }}
        
        /* Stats Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        
        .stat-card {{
            background: var(--bg-card);
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }}
        
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: var(--accent);
        }}
        
        .stat-label {{
            color: var(--text-secondary);
            font-size: 0.9em;
        }}
        
        /* Tables */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        
        th, td {{
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}
        
        th {{
            background: var(--bg-card);
            color: var(--accent-secondary);
            font-weight: 600;
        }}
        
        tr:hover {{
            background: rgba(14, 165, 233, 0.1);
        }}
        
        /* Progress bars */
        .progress-bar {{
            background: var(--bg-card);
            border-radius: 4px;
            height: 20px;
            overflow: hidden;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--accent-secondary), var(--success));
            transition: width 0.3s;
        }}
        
        /* Category Tree */
        .category-tree {{
            max-height: 600px;
            overflow-y: auto;
        }}
        
        .tree-section {{
            margin-bottom: 10px;
        }}
        
        .tree-section > summary {{
            cursor: pointer;
            padding: 10px;
            background: var(--bg-card);
            border-radius: 6px;
            list-style: none;
        }}
        
        .tree-section > summary::-webkit-details-marker {{
            display: none;
        }}
        
        .tree-list {{
            list-style: none;
            padding-left: 20px;
            margin: 5px 0;
        }}
        
        .tree-list li {{
            padding: 4px 0;
        }}
        
        .tree-list a {{
            color: var(--accent-secondary);
            text-decoration: none;
        }}
        
        .tree-list a:hover {{
            text-decoration: underline;
        }}
        
        .count {{
            color: var(--text-secondary);
            font-size: 0.85em;
        }}
        
        .folder-icon {{
            margin-right: 5px;
        }}
        
        .leaf::before {{
            content: "📄 ";
        }}
        
        .more-items {{
            color: var(--text-secondary);
            font-style: italic;
        }}
        
        /* Quality indicators */
        .quality-good {{ color: var(--success); }}
        .quality-warn {{ color: var(--warning); }}
        .quality-bad {{ color: var(--error); }}
        
        /* Links */
        a {{
            color: var(--accent-secondary);
        }}
        
        /* Badges */
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: 600;
        }}
        
        .badge-success {{ background: var(--success); color: #000; }}
        .badge-warning {{ background: var(--warning); color: #000; }}
        .badge-error {{ background: var(--error); color: #fff; }}
        .badge-info {{ background: var(--accent-secondary); color: #000; }}
        
        /* Empty state */
        .empty-state {{
            text-align: center;
            padding: 40px;
            color: var(--text-secondary);
        }}
        
        .empty-state .icon {{
            font-size: 3em;
            margin-bottom: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔍 Scrape Data Viewer</h1>
            <p class="timestamp">Generated: {now}</p>
        </header>
        
        <div class="nav-tabs">
            <button class="nav-tab active" onclick="showSection('overview')">📊 Overview</button>
            <button class="nav-tab" onclick="showSection('coverage')">🎯 Coverage</button>
            <button class="nav-tab" onclick="showSection('categories')">🗂️ Categories</button>
            <button class="nav-tab" onclick="showSection('progress')">⏳ Scrape Progress</button>
            <button class="nav-tab" onclick="showSection('quality')">✅ Data Quality</button>
            <button class="nav-tab" onclick="showSection('products')">📦 Products</button>
        </div>
        
        <div id="overview" class="section active">
            {overview_html}
        </div>
        
        <div id="coverage" class="section">
            {coverage_html}
        </div>
        
        <div id="categories" class="section">
            {category_tree_html}
        </div>
        
        <div id="progress" class="section">
            {scrape_progress_html}
        </div>
        
        <div id="quality" class="section">
            {quality_html}
        </div>
        
        <div id="products" class="section">
            {products_html}
        </div>
    </div>
    
    <script>
        function showSection(sectionId) {{
            // Hide all sections
            document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
            
            // Show selected section
            document.getElementById(sectionId).classList.add('active');
            event.target.classList.add('active');
        }}
    </script>
</body>
</html>
"""


def _build_overview_section(db_stats: Dict, category_data: Dict, coverage_data: Dict) -> str:
    """Build the overview section with key stats."""
    
    if not db_stats.get("exists"):
        db_html = '<div class="empty-state"><div class="icon">📭</div><p>No database found. Run the scraper first.</p></div>'
    else:
        categories_scraped = len(db_stats.get("by_category", {}))
        db_html = f"""
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{db_stats.get('total_products', 0):,}</div>
                <div class="stat-label">Total Products</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{categories_scraped}</div>
                <div class="stat-label">Categories Scraped</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(db_stats.get('top_brands', []))}</div>
                <div class="stat-label">Unique Brands</div>
            </div>
        </div>
        """
    
    if not category_data.get("exists"):
        cat_html = '<p class="empty-state">No category discovery data found.</p>'
    else:
        stats = category_data.get("stats", {})
        cat_html = f"""
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{stats.get('total', 0):,}</div>
                <div class="stat-label">Discovered Categories</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('leaf_count', 0):,}</div>
                <div class="stat-label">Leaf Categories</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats.get('max_depth', 0)}</div>
                <div class="stat-label">Max Depth</div>
            </div>
        </div>
        """
    
    # Coverage summary
    if coverage_data.get("exists"):
        coverage_pct = coverage_data.get("coverage_pct", 0)
        scraped = coverage_data.get("scraped_count", 0)
        not_scraped = coverage_data.get("not_scraped_count", 0)
        
        if coverage_pct >= 50:
            pct_class = "quality-good"
        elif coverage_pct >= 20:
            pct_class = "quality-warn"
        else:
            pct_class = "quality-bad"
        
        coverage_html = f"""
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value {pct_class}">{coverage_pct:.1f}%</div>
                <div class="stat-label">Coverage</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: var(--success);">{scraped}</div>
                <div class="stat-label">Scraped</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: var(--text-secondary);">{not_scraped}</div>
                <div class="stat-label">Not Scraped</div>
            </div>
        </div>
        <div class="progress-bar" style="height: 12px; margin-top: 10px;">
            <div class="progress-fill" style="width: {coverage_pct:.0f}%"></div>
        </div>
        """
    else:
        coverage_html = '<p class="empty-state">Run category discovery to see coverage.</p>'
    
    return f"""
    <div class="card">
        <h2>📦 Scraped Products</h2>
        {db_html}
    </div>
    <div class="card">
        <h2>🗂️ Discovered Categories</h2>
        {cat_html}
        <p class="timestamp">Last updated: {category_data.get('file_modified', 'N/A')}</p>
    </div>
    <div class="card">
        <h2>🎯 Scrape Coverage</h2>
        <p class="timestamp">Leaf categories with scraped products vs total discovered</p>
        {coverage_html}
    </div>
    """


def _build_scrape_progress_section(scrape_states: List[Dict], db_stats: Dict) -> str:
    """Build the scrape progress section."""
    
    if not scrape_states:
        return """
        <div class="card">
            <h2>⏳ Scrape Progress</h2>
            <div class="empty-state">
                <div class="icon">📭</div>
                <p>No scrape state data found. Run the scraper to see progress.</p>
            </div>
        </div>
        """
    
    rows = []
    for state in scrape_states:
        category = state.get("category", "unknown")
        pages_scraped = state.get("last_page_scraped", 0) or 0
        total_pages = state.get("total_pages_found") or 0
        last_scraped = state.get("last_scraped_at", "Never")
        product_count = db_stats.get("by_category", {}).get(category, 0)
        
        # Progress percentage
        if total_pages > 0:
            progress = min(100, (pages_scraped / total_pages) * 100)
            progress_html = f"""
            <div class="progress-bar">
                <div class="progress-fill" style="width: {progress:.0f}%"></div>
            </div>
            <small>{pages_scraped}/{total_pages} pages ({progress:.0f}%)</small>
            """
        else:
            progress_html = f"<span class='badge badge-info'>{pages_scraped} pages</span>"
        
        rows.append(f"""
        <tr>
            <td><strong>{escape_html(category)}</strong></td>
            <td>{product_count:,}</td>
            <td>{progress_html}</td>
            <td>{escape_html(str(last_scraped) if last_scraped else 'Never')}</td>
        </tr>
        """)
    
    return f"""
    <div class="card">
        <h2>⏳ Scrape Progress by Category</h2>
        <table>
            <thead>
                <tr>
                    <th>Category</th>
                    <th>Products</th>
                    <th>Progress</th>
                    <th>Last Scraped</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    </div>
    """


def _build_category_section(category_data: Dict) -> str:
    """Build the category tree section."""
    
    if not category_data.get("exists"):
        return """
        <div class="card">
            <h2>🗂️ Discovered Categories</h2>
            <div class="empty-state">
                <div class="icon">📭</div>
                <p>No category discovery data found.</p>
                <p>Run: <code>python -m scrape.discover_categories --output data/discovered_categories.json</code></p>
            </div>
        </div>
        """
    
    categories = category_data.get("categories", [])
    tree_html = build_category_tree_html(categories, max_depth=5)
    
    # Group stats by top-level
    by_top_level: Dict[str, int] = defaultdict(int)
    for cat in categories:
        segments = cat.get("segments")
        if segments:
            by_top_level[segments[0]] += 1
    
    summary_rows = "".join(
        f"<tr><td>{escape_html(k.replace('-', ' ').title())}</td><td>{v}</td></tr>"
        for k, v in sorted(by_top_level.items(), key=lambda x: -x[1])
    )
    
    return f"""
    <div class="card">
        <h2>🗂️ Category Summary</h2>
        <table>
            <thead><tr><th>Top-Level Category</th><th>Subcategories</th></tr></thead>
            <tbody>{summary_rows}</tbody>
        </table>
    </div>
    <div class="card">
        <h2>🌳 Category Tree</h2>
        <p class="timestamp">Click to expand/collapse branches. Links open on bike-components.de</p>
        {tree_html}
    </div>
    """


def _build_coverage_section(coverage_data: Dict) -> str:
    """Build the category coverage section showing scraped vs not scraped as a tree."""
    
    if not coverage_data.get("exists"):
        return """
        <div class="card">
            <h2>🎯 Category Coverage</h2>
            <div class="empty-state">
                <div class="icon">📭</div>
                <p>No coverage data available.</p>
                <p>Run category discovery and scrape some categories first.</p>
            </div>
        </div>
        """
    
    scraped_count = coverage_data.get("scraped_count", 0)
    not_scraped_count = coverage_data.get("not_scraped_count", 0)
    coverage_pct = coverage_data.get("coverage_pct", 0)
    
    # Stats
    stats_html = f"""
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-value" style="color: var(--success);">{scraped_count}</div>
            <div class="stat-label">Categories Scraped</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color: var(--text-secondary);">{not_scraped_count}</div>
            <div class="stat-label">Not Yet Scraped</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{coverage_pct:.1f}%</div>
            <div class="stat-label">Overall Coverage</div>
        </div>
    </div>
    <div class="progress-bar" style="margin-bottom: 20px;">
        <div class="progress-fill" style="width: {coverage_pct:.0f}%"></div>
    </div>
    """
    
    # Build hierarchical tree from all categories
    scraped_cats = coverage_data.get("scraped_categories", [])
    not_scraped_cats = coverage_data.get("not_scraped_categories", [])
    all_cats = scraped_cats + not_scraped_cats
    
    # Mark each category with its scraped status
    scraped_paths = {cat.get("path") for cat in scraped_cats}
    
    # Build tree structure
    tree = _build_coverage_tree(all_cats, scraped_paths)
    tree_html = _render_coverage_tree_html(tree)
    
    if not tree_html:
        tree_html = '<p class="empty-state">No categories to display.</p>'
    
    return f"""
    <div class="card">
        <h2>🎯 Coverage Overview</h2>
        {stats_html}
    </div>
    <div class="card">
        <h2>🌳 Category Coverage Tree</h2>
        <p class="timestamp">Expand to see coverage by category. <span style="color: var(--success);">✓ = scraped</span>, <span style="color: var(--text-secondary);">○ = not scraped</span></p>
        <div class="category-tree" style="max-height: 600px; overflow-y: auto;">
            {tree_html}
        </div>
    </div>
    """


def _build_coverage_tree(categories: List[Dict], scraped_paths: set) -> Dict:
    """Build a nested tree with coverage counts at each level."""
    tree: Dict = {}
    
    for cat in categories:
        segments = cat.get("segments", [])
        path = cat.get("path", "")
        is_scraped = path in scraped_paths
        
        current = tree
        for i, segment in enumerate(segments):
            if segment not in current:
                current[segment] = {
                    "_children": {},
                    "_total": 0,
                    "_scraped": 0,
                    "_is_leaf": False,
                    "_meta": None,
                }
            
            # Increment counts for this node and all ancestors
            current[segment]["_total"] += 1
            if is_scraped:
                current[segment]["_scraped"] += 1
            
            # If this is the leaf level, store metadata
            if i == len(segments) - 1:
                current[segment]["_is_leaf"] = True
                current[segment]["_meta"] = cat
                current[segment]["_is_scraped"] = is_scraped
            
            current = current[segment]["_children"]
    
    return tree


def _render_coverage_tree_html(tree: Dict, depth: int = 0) -> str:
    """Render the coverage tree as nested HTML with scraped/total counts."""
    html_parts = []
    
    for key in sorted(tree.keys()):
        if key.startswith("_"):
            continue
        
        node = tree[key]
        children = node.get("_children", {})
        total = node.get("_total", 0)
        scraped = node.get("_scraped", 0)
        is_leaf = node.get("_is_leaf", False)
        meta = node.get("_meta")
        is_scraped = node.get("_is_scraped", False)
        
        name = key.replace("-", " ").title()
        child_keys = [k for k in children.keys() if not k.startswith("_")]
        has_children = len(child_keys) > 0
        
        # Calculate coverage percentage for this branch
        pct = (scraped / total * 100) if total > 0 else 0
        
        # Choose color based on coverage
        if pct >= 100:
            count_class = "quality-good"
            icon = "✅"
        elif pct >= 50:
            count_class = "quality-warn"
            icon = "🟡"
        elif pct > 0:
            count_class = "quality-warn"
            icon = "🟠"
        else:
            count_class = "quality-bad"
            icon = "⭕"
        
        if is_leaf and not has_children:
            # Leaf node - show as single item with status
            url = meta.get("url", "") if meta else ""
            product_count = meta.get("product_count", 0) if meta else 0
            
            if is_scraped:
                status_icon = '<span style="color: var(--success);">✓</span>'
                product_badge = f' <span class="badge badge-success">{product_count:,} products</span>' if product_count else ''
            else:
                status_icon = '<span style="color: var(--text-secondary);">○</span>'
                product_badge = ''
            
            if url:
                html_parts.append(f'<li class="leaf">{status_icon} <a href="{escape_html(url)}" target="_blank">{escape_html(name)}</a>{product_badge}</li>')
            else:
                html_parts.append(f'<li class="leaf">{status_icon} {escape_html(name)}{product_badge}</li>')
        else:
            # Branch node - show with expandable children
            count_badge = f'<span class="{count_class}" style="font-weight: bold;">{scraped}/{total}</span>'
            
            # Small progress bar
            progress_html = f'<span style="display: inline-block; width: 60px; height: 8px; background: var(--bg-card); border-radius: 4px; margin-left: 8px; vertical-align: middle;"><span style="display: block; height: 100%; width: {pct:.0f}%; background: {"var(--success)" if pct >= 100 else "var(--accent-secondary)"}; border-radius: 4px;"></span></span>'
            
            # Determine if this should be open by default (only top level)
            open_attr = " open" if depth == 0 else ""
            
            html_parts.append(f'<li class="has-children">')
            html_parts.append(f'<details{open_attr}><summary>{icon} <strong>{escape_html(name)}</strong> {count_badge}{progress_html}</summary>')
            html_parts.append('<ul class="tree-list">')
            html_parts.append(_render_coverage_tree_html(children, depth + 1))
            html_parts.append('</ul></details></li>')
    
    return "\n".join(html_parts)


def _build_quality_section(quality: Dict, db_stats: Dict) -> str:
    """Build the data quality section."""
    
    if not db_stats.get("exists"):
        return """
        <div class="card">
            <h2>✅ Data Quality</h2>
            <div class="empty-state">
                <div class="icon">📭</div>
                <p>No data to analyze. Run the scraper first.</p>
            </div>
        </div>
        """
    
    total = db_stats.get("total_products", 1) or 1
    
    # Missing fields table
    missing = quality.get("missing_fields", {})
    missing_rows = []
    for field, count in sorted(missing.items(), key=lambda x: -x[1]):
        pct = (count / total) * 100
        if pct < 5:
            badge = "badge-success"
            status = "Good"
        elif pct < 20:
            badge = "badge-warning"
            status = "Warning"
        else:
            badge = "badge-error"
            status = "Bad"
        
        missing_rows.append(f"""
        <tr>
            <td>{escape_html(field)}</td>
            <td>{count:,} ({pct:.1f}%)</td>
            <td><span class="badge {badge}">{status}</span></td>
        </tr>
        """)
    
    # Spec tables coverage
    spec_counts = quality.get("spec_table_counts", {})
    spec_rows = "".join(
        f"<tr><td>{escape_html(table)}</td><td>{count:,}</td></tr>"
        for table, count in sorted(spec_counts.items())
    )
    
    # Duplicate check
    duplicates = quality.get("duplicate_urls", [])
    dup_html = f'<span class="badge badge-success">No duplicates</span>' if not duplicates else f'<span class="badge badge-error">{len(duplicates)} duplicates found</span>'
    
    return f"""
    <div class="card">
        <h2>✅ Data Quality Overview</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{quality.get('missing_specs', 0):,}</div>
                <div class="stat-label">Missing Specs JSON</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{dup_html}</div>
                <div class="stat-label">Duplicate URLs</div>
            </div>
        </div>
    </div>
    <div class="card">
        <h2>📋 Missing Fields Analysis</h2>
        <table>
            <thead><tr><th>Field</th><th>Missing Count</th><th>Status</th></tr></thead>
            <tbody>{''.join(missing_rows)}</tbody>
        </table>
    </div>
    <div class="card">
        <h2>🔧 Spec Table Coverage</h2>
        <table>
            <thead><tr><th>Spec Table</th><th>Records</th></tr></thead>
            <tbody>{spec_rows}</tbody>
        </table>
    </div>
    """


def _build_products_section(sample_products: List[Dict], db_stats: Dict) -> str:
    """Build the products preview section."""
    
    if not db_stats.get("exists") or not sample_products:
        return """
        <div class="card">
            <h2>📦 Sample Products</h2>
            <div class="empty-state">
                <div class="icon">📭</div>
                <p>No products found. Run the scraper first.</p>
            </div>
        </div>
        """
    
    # Products by category
    by_category = db_stats.get("by_category", {})
    category_rows = "".join(
        f"<tr><td>{escape_html(cat)}</td><td>{count:,}</td></tr>"
        for cat, count in sorted(by_category.items(), key=lambda x: -x[1])
    )
    
    # Sample products table
    product_rows = []
    for p in sample_products:
        url = p.get("url", "")
        name = p.get("name", "Unknown")
        link = f'<a href="{escape_html(url)}" target="_blank">{escape_html(name[:50])}...</a>' if len(name) > 50 else f'<a href="{escape_html(url)}" target="_blank">{escape_html(name)}</a>'
        
        product_rows.append(f"""
        <tr>
            <td>{escape_html(p.get('category', ''))}</td>
            <td>{link}</td>
            <td>{escape_html(p.get('brand', '') or '-')}</td>
            <td>{escape_html(p.get('price_text', '') or '-')}</td>
        </tr>
        """)
    
    # Top brands
    brands = db_stats.get("top_brands", [])
    brand_rows = "".join(
        f"<tr><td>{escape_html(brand)}</td><td>{count:,}</td></tr>"
        for brand, count in brands[:15]
    )
    
    return f"""
    <div class="card">
        <h2>📊 Products by Category</h2>
        <table>
            <thead><tr><th>Category</th><th>Product Count</th></tr></thead>
            <tbody>{category_rows}</tbody>
        </table>
    </div>
    <div class="card">
        <h2>🏷️ Top Brands</h2>
        <table>
            <thead><tr><th>Brand</th><th>Product Count</th></tr></thead>
            <tbody>{brand_rows}</tbody>
        </table>
    </div>
    <div class="card">
        <h2>📦 Recent Products (Sample)</h2>
        <table>
            <thead><tr><th>Category</th><th>Name</th><th>Brand</th><th>Price</th></tr></thead>
            <tbody>{''.join(product_rows)}</tbody>
        </table>
    </div>
    """


# =============================================================================
# Auto-regeneration API
# =============================================================================

def regenerate_report(open_browser: bool = False) -> Path:
    """Regenerate the HTML report from current data.
    
    This can be called from other modules (e.g., after scraping).
    
    Args:
        open_browser: Whether to open the report in a browser
        
    Returns:
        Path to the generated HTML file
    """
    db_stats = get_db_stats(DB_PATH)
    scrape_states = get_scrape_state(DB_PATH)
    quality = get_data_quality(DB_PATH)
    sample_products = get_sample_products(DB_PATH, limit=20)
    category_data = load_discovered_categories(CATEGORIES_JSON)
    coverage_data = compute_category_coverage(category_data, db_stats)
    
    html = generate_html(db_stats, scrape_states, quality, sample_products, category_data, coverage_data)
    
    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    
    if open_browser:
        webbrowser.open(f"file://{OUTPUT_HTML.absolute()}")
    
    return OUTPUT_HTML


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="View scraped data and category discovery results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--open", "-o", action="store_true", help="Open in browser after generating")
    parser.add_argument("--output", default=str(OUTPUT_HTML), help="Output HTML file path")
    parser.add_argument("--db", default=str(DB_PATH), help="Database path")
    parser.add_argument("--categories-json", default=str(CATEGORIES_JSON), help="Categories JSON path")
    
    args = parser.parse_args()
    
    db_path = Path(args.db)
    categories_json = Path(args.categories_json)
    output_path = Path(args.output)
    
    print("🔍 Scrape Data Viewer")
    print("=" * 50)
    
    # Load data
    print(f"Loading database: {db_path}")
    db_stats = get_db_stats(db_path)
    scrape_states = get_scrape_state(db_path)
    quality = get_data_quality(db_path)
    sample_products = get_sample_products(db_path, limit=20)
    
    print(f"Loading categories: {categories_json}")
    category_data = load_discovered_categories(categories_json)
    
    print("Computing coverage...")
    coverage_data = compute_category_coverage(category_data, db_stats)
    
    # Generate HTML
    print(f"Generating HTML report...")
    html = generate_html(db_stats, scrape_states, quality, sample_products, category_data, coverage_data)
    
    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"✅ Report saved to: {output_path}")
    
    # Summary
    if db_stats.get("exists"):
        print(f"   📦 {db_stats.get('total_products', 0):,} products in {len(db_stats.get('by_category', {}))} categories")
    else:
        print("   ⚠️  No database found")
    
    if category_data.get("exists"):
        stats = category_data.get("stats", {})
        print(f"   🗂️  {stats.get('total', 0):,} discovered categories ({stats.get('leaf_count', 0)} leaf)")
    else:
        print("   ⚠️  No category discovery data found")
    
    if coverage_data.get("exists"):
        print(f"   🎯 Coverage: {coverage_data.get('scraped_count', 0)}/{coverage_data.get('total_leaf', 0)} leaf categories ({coverage_data.get('coverage_pct', 0):.1f}%)")
    
    # Open in browser
    if args.open:
        print(f"\n🌐 Opening in browser...")
        webbrowser.open(f"file://{output_path.absolute()}")


if __name__ == "__main__":
    main()
