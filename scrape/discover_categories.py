"""Automatic category discovery from bike-components.de sitemap.

This module fetches the sitemap and extracts all category URLs,
organizing them into a hierarchical structure.

Usage:
    python -m scrape.discover_categories
    python -m scrape.discover_categories --min-depth 3 --output data/categories.json
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrape.config import HEADERS

__all__ = [
    "fetch_sitemap_urls",
    "parse_category_url",
    "build_category_tree",
    "discover_categories",
    "generate_config_snippet",
]

SITEMAP_INDEX_URL = "https://www.bike-components.de/assets/sitemap/main-en.xml"
OTHERS_SITEMAP_URL = "https://www.bike-components.de/assets/sitemap/others-en.xml"


def fetch_sitemap_urls(sitemap_url: str) -> List[str]:
    """Fetch and parse a sitemap XML, returning all URLs."""
    resp = requests.get(sitemap_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

    urls = []
    for loc in root.findall('.//sm:loc', ns):
        if loc.text:
            urls.append(loc.text)

    return urls


def parse_category_url(url: str) -> Optional[Dict]:
    """Parse a category URL into its components.
    
    Returns dict with:
        - url: full URL
        - path: URL path without domain
        - segments: list of path segments
        - depth: number of segments (depth in hierarchy)
        - key: suggested config key (snake_case)
        - parent_key: parent category key
    """
    parsed = urlparse(url)
    path = parsed.path.strip('/')

    # Skip non-English URLs
    if not path.startswith('en/'):
        return None

    # Remove 'en/' prefix
    path = path[3:]
    segments = [s for s in path.split('/') if s]

    if not segments:
        return None

    # Generate a key from the last segment(s)
    if len(segments) >= 2:
        # Use last two segments for uniqueness: "drivetrain_chains"
        key = '_'.join(segments[-2:]).replace('-', '_')
    else:
        key = segments[-1].replace('-', '_')

    # Parent key
    parent_key = None
    if len(segments) >= 2:
        parent_key = '_'.join(segments[:-1]).replace('-', '_')

    return {
        'url': url,
        'path': path,
        'segments': segments,
        'depth': len(segments),
        'key': key,
        'parent_key': parent_key,
        'name': segments[-1].replace('-', ' ').title(),
    }


def build_category_tree(categories: List[Dict]) -> Dict:
    """Build a hierarchical tree from flat category list."""
    tree: Dict = {}

    for cat in sorted(categories, key=lambda x: x['depth']):
        segments = cat['segments']
        current = tree

        for i, segment in enumerate(segments):
            if segment not in current:
                current[segment] = {
                    '_meta': None,
                    '_children': {}
                }

            if i == len(segments) - 1:
                current[segment]['_meta'] = cat

            current = current[segment]['_children']

    return tree


def print_tree(tree: Dict, indent: int = 0, max_depth: int = 4) -> None:
    """Pretty print the category tree."""
    for key, value in sorted(tree.items()):
        if key.startswith('_'):
            continue

        meta = value.get('_meta', {})
        children = value.get('_children', {})
        child_count = len([k for k in children.keys() if not k.startswith('_')])

        prefix = "  " * indent
        name = meta.get('name', key) if meta else key

        if child_count > 0:
            print(f"{prefix}📁 {name} ({child_count} subcategories)")
        else:
            print(f"{prefix}📄 {name}")

        if indent < max_depth - 1:
            print_tree(children, indent + 1, max_depth)


def discover_categories(
    min_depth: int = 2,
    max_depth: int = 10,
    top_level_filter: Optional[List[str]] = None,
) -> Dict:
    """Discover all categories from the sitemap.
    
    Args:
        min_depth: Minimum URL depth to include (2 = /en/components/)
        max_depth: Maximum URL depth to include
        top_level_filter: Only include categories under these top-level paths
                         e.g., ['components', 'apparel']
    
    Returns:
        Dict with:
            - categories: list of all category dicts
            - tree: hierarchical tree structure
            - by_depth: categories grouped by depth
            - leaf_categories: categories with no children (actual product listings)
    """
    print("Fetching sitemap...")
    urls = fetch_sitemap_urls(OTHERS_SITEMAP_URL)
    print(f"Found {len(urls)} URLs in sitemap")

    # Parse all category URLs
    categories = []
    for url in urls:
        cat = parse_category_url(url)
        if cat and min_depth <= cat['depth'] <= max_depth:
            if top_level_filter:
                if cat['segments'][0] not in top_level_filter:
                    continue
            categories.append(cat)

    print(f"Parsed {len(categories)} category URLs")

    # Group by depth
    by_depth: Dict[int, List[Dict]] = defaultdict(list)
    for cat in categories:
        by_depth[cat['depth']].append(cat)

    # Find leaf categories (no children)
    all_paths = {cat['path'] for cat in categories}
    leaf_categories = []
    for cat in categories:
        # Check if any other path starts with this one
        is_parent = any(
            other_path.startswith(cat['path'] + '/')
            for other_path in all_paths
            if other_path != cat['path']
        )
        if not is_parent:
            leaf_categories.append(cat)

    # Build tree
    tree = build_category_tree(categories)

    return {
        'categories': categories,
        'tree': tree,
        'by_depth': dict(by_depth),
        'leaf_categories': leaf_categories,
        'stats': {
            'total': len(categories),
            'leaf_count': len(leaf_categories),
            'max_depth': max(cat['depth'] for cat in categories) if categories else 0,
        }
    }


def generate_config_snippet(categories: List[Dict], limit: int = 20) -> str:
    """Generate a CATEGORY_URLS config snippet for selected categories."""
    lines = ["CATEGORY_URLS: Dict[str, str] = {"]

    for cat in categories[:limit]:
        lines.append(f'    "{cat["key"]}": "{cat["url"]}",')

    if len(categories) > limit:
        lines.append(f"    # ... and {len(categories) - limit} more")

    lines.append("}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discover categories from bike-components.de sitemap",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Show category tree
    python -m scrape.discover_categories
    
    # Only show components and tools
    python -m scrape.discover_categories --filter components tools-maintenance
    
    # Export leaf categories to JSON
    python -m scrape.discover_categories --output data/categories.json
    
    # Show deeper hierarchy
    python -m scrape.discover_categories --max-depth 5
        """,
    )

    parser.add_argument(
        "--min-depth",
        type=int,
        default=2,
        help="Minimum category depth (default: 2)",
    )

    parser.add_argument(
        "--max-depth",
        type=int,
        default=10,
        help="Maximum category depth (default: 10)",
    )

    parser.add_argument(
        "--filter",
        nargs="+",
        dest="top_level_filter",
        help="Only show categories under these top-level paths (e.g., components apparel)",
    )

    parser.add_argument(
        "--leaves-only",
        action="store_true",
        help="Only show leaf categories (actual product listings)",
    )

    parser.add_argument(
        "--output",
        help="Save results to JSON file",
    )

    parser.add_argument(
        "--generate-config",
        action="store_true",
        help="Generate CATEGORY_URLS config snippet",
    )

    parser.add_argument(
        "--tree-depth",
        type=int,
        default=3,
        help="Max depth to show in tree view (default: 3)",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    results = discover_categories(
        min_depth=args.min_depth,
        max_depth=args.max_depth,
        top_level_filter=args.top_level_filter,
    )

    print()
    print("=" * 60)
    print("CATEGORY DISCOVERY RESULTS")
    print("=" * 60)
    print(f"Total categories: {results['stats']['total']}")
    print(f"Leaf categories (product pages): {results['stats']['leaf_count']}")
    print(f"Max depth: {results['stats']['max_depth']}")

    # Show by depth
    print("\nCategories by depth:")
    for depth in sorted(results['by_depth'].keys()):
        count = len(results['by_depth'][depth])
        print(f"  Depth {depth}: {count} categories")

    # Show tree
    print("\n" + "-" * 60)
    print("CATEGORY TREE")
    print("-" * 60)
    print_tree(results['tree'], max_depth=args.tree_depth)

    # Show leaf categories
    if args.leaves_only:
        print("\n" + "-" * 60)
        print(f"LEAF CATEGORIES ({len(results['leaf_categories'])})")
        print("-" * 60)
        for cat in results['leaf_categories'][:50]:
            print(f"  {cat['key']}: {cat['url']}")
        if len(results['leaf_categories']) > 50:
            print(f"  ... and {len(results['leaf_categories']) - 50} more")

    # Generate config
    if args.generate_config:
        print("\n" + "-" * 60)
        print("SUGGESTED CATEGORY_URLS CONFIG")
        print("-" * 60)
        # Use leaf categories for the config
        snippet = generate_config_snippet(results['leaf_categories'], limit=30)
        print(snippet)

    # Save to file
    if args.output:
        # Make JSON serializable
        output_data = {
            'stats': results['stats'],
            'categories': results['categories'],
            'leaf_categories': results['leaf_categories'],
        }

        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
