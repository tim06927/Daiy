"""Automatic category field discovery tool.

This module samples products from a category and discovers which spec fields
are commonly available, then suggests a schema for the CATEGORY_SPECS registry.

Usage:
    python -m scrape.discover_fields chains --sample-size 30
    python -m scrape.discover_fields cassettes --sample-size 50 --min-frequency 0.3
"""

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bs4 import BeautifulSoup

from scrape.config import BASE_URL, CATEGORY_URLS
from scrape.html_utils import extract_next_page_url, is_product_url
from scrape.scraper import fetch_html

__all__ = [
    "to_snake_case",
    "extract_all_spec_labels",
    "sample_products",
    "discover_category_fields",
    "print_results",
]


def to_snake_case(label: str) -> str:
    """Convert a spec label to a valid Python/SQL column name."""
    # Remove special characters, convert to lowercase
    cleaned = re.sub(r'[^\w\s]', '', label.lower())
    # Replace spaces with underscores
    cleaned = re.sub(r'\s+', '_', cleaned.strip())
    # Remove consecutive underscores
    cleaned = re.sub(r'_+', '_', cleaned)
    return cleaned


def extract_all_spec_labels(html: str) -> Dict[str, str]:
    """Extract all spec labels and their values from a product page.
    
    Returns dict of {label: value} for all specs found.
    """
    soup = BeautifulSoup(html, "html.parser")

    specs: Dict[str, str] = {}

    # Primary location: product description block (multiple possible selectors)
    desc_containers = [
        soup.select_one('div.description[data-overlay="product-description"] div.site-text'),
        soup.select_one('div.description div.site-text'),
        soup.select_one('div.description'),
    ]

    for desc_container in desc_containers:
        if desc_container:
            for dl in desc_container.find_all("dl"):
                dts = dl.find_all("dt")
                dds = dl.find_all("dd")
                for dt, dd in zip(dts, dds):
                    key = dt.get_text(strip=True).rstrip(":")
                    value = " ".join(dd.stripped_strings)
                    if key and value and key not in specs:
                        specs[key] = value
            if specs:  # Found specs, stop looking
                break

    # Fallback: look for any dl/dt/dd on the page
    if not specs:
        for dl in soup.find_all("dl"):
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")
            for dt, dd in zip(dts, dds):
                key = dt.get_text(strip=True).rstrip(":")
                value = " ".join(dd.stripped_strings)
                if key and value and key not in specs:
                    specs[key] = value

    # Also check for specs in tables
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True).rstrip(":")
                value = cells[1].get_text(strip=True)
                if key and value and key not in specs:
                    specs[key] = value

    return specs


def get_product_links_from_page(html: str) -> List[str]:
    """Extract product URLs from a category page."""
    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []

    for a in soup.select("a[href^='/en/']"):
        href = a.get("href")
        if href and isinstance(href, str) and is_product_url(href):
            full_url = BASE_URL + href
            if full_url not in links:
                links.append(full_url)

    return links


def sample_products(
    category_url: str,
    sample_size: int = 30,
    max_pages: int = 5,
) -> List[str]:
    """Get a sample of product URLs from a category, spread across pages."""
    product_urls: List[str] = []
    current_url: Optional[str] = category_url
    page = 0

    while current_url and len(product_urls) < sample_size and page < max_pages:
        page += 1
        print(f"  Scanning page {page}: {current_url}")

        html = fetch_html(current_url)
        soup = BeautifulSoup(html, "html.parser")

        links = get_product_links_from_page(html)

        # Take proportional sample from each page
        remaining = sample_size - len(product_urls)
        per_page = max(remaining // (max_pages - page + 1), 5)
        product_urls.extend(links[:per_page])

        # Get next page
        next_url = extract_next_page_url(soup, current_url)
        current_url = next_url if next_url != current_url else None

    return product_urls[:sample_size]


def discover_category_fields(
    category_key: str,
    sample_size: int = 30,
    min_frequency: float = 0.3,
    max_pages: int = 5,
) -> Dict[str, Any]:
    """Discover common spec fields for a category.
    
    Args:
        category_key: Category identifier (must be in CATEGORY_URLS)
        sample_size: Number of products to sample
        min_frequency: Minimum frequency (0-1) to include a field
        max_pages: Maximum category pages to scan for samples
        
    Returns:
        Dict with discovery results including suggested schema
    """
    if category_key not in CATEGORY_URLS:
        raise ValueError(f"Unknown category: {category_key}. Available: {list(CATEGORY_URLS.keys())}")

    category_url = CATEGORY_URLS[category_key]
    print(f"\nDiscovering fields for category: {category_key}")
    print(f"URL: {category_url}")
    print(f"Sample size: {sample_size}")

    # Step 1: Get sample product URLs
    print("\n[1/3] Sampling product URLs...")
    product_urls = sample_products(category_url, sample_size, max_pages)
    print(f"  Found {len(product_urls)} products to sample")

    # Step 2: Extract specs from each product
    print("\n[2/3] Extracting specs from products...")
    all_specs: List[Dict[str, str]] = []
    label_counter: Counter = Counter()
    label_values: Dict[str, List[str]] = defaultdict(list)

    for i, url in enumerate(product_urls, 1):
        print(f"  [{i}/{len(product_urls)}] {url.split('/')[-2][:40]}...")
        try:
            html = fetch_html(url)
            specs = extract_all_spec_labels(html)
            all_specs.append(specs)

            for label, value in specs.items():
                label_counter[label] += 1
                label_values[label].append(value)
        except Exception as e:
            print(f"    ERROR: {e}")

    total_products = len(all_specs)
    if total_products == 0:
        print("No products could be sampled!")
        return {}

    # Step 3: Analyze frequencies and suggest schema
    print("\n[3/3] Analyzing field frequencies...")

    # If no labels were collected from the sampled products, abort analysis early.
    if not label_counter:
        print("No spec labels were found in sampled products!")
        return {
            "category": category_key,
            "products_sampled": total_products,
            "all_fields": [],
            "suggested_fields": [],
            "suggested_config": None,
        }

    results = {
        "category": category_key,
        "products_sampled": total_products,
        "all_fields": [],
        "suggested_fields": [],
        "suggested_config": None,
    }

    # Sort by frequency
    sorted_labels = sorted(label_counter.items(), key=lambda x: -x[1])

    print(f"\n{'Label':<40} {'Count':>6} {'Freq':>8} {'Include':>8}")
    print("-" * 70)

    suggested_fields: List[Tuple[str, str, float]] = []  # (original_label, column_name, frequency)

    for label, count in sorted_labels:
        freq = count / total_products
        include = "✓" if freq >= min_frequency else ""
        print(f"{label[:40]:<40} {count:>6} {freq:>7.1%} {include:>8}")

        column_name = to_snake_case(label)
        field_info = {
            "label": label,
            "column_name": column_name,
            "count": count,
            "frequency": freq,
            "sample_values": label_values[label][:3],
        }
        results["all_fields"].append(field_info)

        if freq >= min_frequency:
            results["suggested_fields"].append(field_info)
            suggested_fields.append((label, column_name, freq))

    # Generate suggested config
    if suggested_fields:
        config_lines = [
            f'    "{category_key}": {{',
            f'        "spec_table": "{category_key}_specs",',
            '        "field_mappings": {',
        ]

        # Group similar labels (e.g., "Gearing" and "Speed" might mean the same thing)
        for label, column, freq in suggested_fields:
            config_lines.append(f'            "{column}": ["{label}"],  # {freq:.0%}')

        config_lines.append('        },')
        config_lines.append('    },')

        results["suggested_config"] = "\n".join(config_lines)

    return results


def print_results(results: Dict) -> None:
    """Print discovery results in a readable format."""
    if not results:
        return

    print("\n" + "=" * 70)
    print("DISCOVERY RESULTS")
    print("=" * 70)

    print(f"\nCategory: {results['category']}")
    print(f"Products sampled: {results['products_sampled']}")
    print(f"Total unique fields found: {len(results['all_fields'])}")
    print(f"Fields meeting frequency threshold: {len(results['suggested_fields'])}")

    if results.get("suggested_config"):
        print("\n" + "-" * 70)
        print("SUGGESTED CONFIG (paste into scrape/config.py CATEGORY_SPECS):")
        print("-" * 70)
        print(results["suggested_config"])

    print("\n" + "-" * 70)
    print("SUGGESTED SQL TABLE:")
    print("-" * 70)
    table_name = f"{results['category']}_specs"
    print(f"CREATE TABLE IF NOT EXISTS {table_name} (")
    print("    id INTEGER PRIMARY KEY AUTOINCREMENT,")
    print("    product_id INTEGER UNIQUE NOT NULL,")
    for field in results["suggested_fields"]:
        print(f"    {field['column_name']} TEXT,  -- {field['label']}")
    print("    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE")
    print(");")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discover category-specific fields from bike-components.de",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Discover fields for chains category
    python -m scrape.discover_fields chains
    
    # Sample more products for better accuracy
    python -m scrape.discover_fields cassettes --sample-size 50
    
    # Lower frequency threshold to include more fields
    python -m scrape.discover_fields mtb_gloves --min-frequency 0.2
    
    # Discover all categories
    python -m scrape.discover_fields --all
        """,
    )

    parser.add_argument(
        "category",
        nargs="?",
        choices=list(CATEGORY_URLS.keys()),
        help=f"Category to discover. Choices: {list(CATEGORY_URLS.keys())}",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Discover fields for all categories",
    )

    parser.add_argument(
        "--sample-size",
        type=int,
        default=30,
        help="Number of products to sample (default: 30)",
    )

    parser.add_argument(
        "--min-frequency",
        type=float,
        default=0.3,
        help="Minimum frequency (0-1) to include a field (default: 0.3 = 30%%)",
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Maximum category pages to scan for samples (default: 5)",
    )

    parser.add_argument(
        "--output",
        help="Write results to JSON file",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.category and not args.all:
        print("Error: Must specify a category or use --all")
        print(f"Available categories: {list(CATEGORY_URLS.keys())}")
        sys.exit(1)

    categories = list(CATEGORY_URLS.keys()) if args.all else [args.category]

    all_results = {}
    for category in categories:
        results = discover_category_fields(
            category,
            sample_size=args.sample_size,
            min_frequency=args.min_frequency,
            max_pages=args.max_pages,
        )
        all_results[category] = results
        print_results(results)

    if args.output:
        import json
        # Convert to JSON-serializable format
        for cat, res in all_results.items():
            if res:
                for field in res.get("all_fields", []):
                    field["frequency"] = round(field["frequency"], 3)

        with open(args.output, "w") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
