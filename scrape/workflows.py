"""High-level scraping workflows.

This module contains orchestration logic for complex multi-step operations
like discover-and-scrape workflows.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from scrape.config import CATEGORY_URLS
from scrape.db import get_existing_urls, init_db
from scrape.models import Product
from scrape.scraper import scrape_category

__all__ = [
    "get_leaf_categories_under_path",
    "run_field_discovery_for_category",
    "scrape_dynamic_category",
    "discover_and_scrape_workflow",
]


def get_leaf_categories_under_path(parent_path: str) -> List[Dict[str, Any]]:
    """Find all leaf categories under a given parent path.
    
    Args:
        parent_path: Path like 'components/drivetrain' or 'accessories'
        
    Returns:
        List of leaf category dicts with 'key', 'url', 'name', 'path'
    """
    from scrape.discover_categories import discover_categories
    
    # Normalize path
    parent_path = parent_path.strip('/').lower()
    segments = parent_path.split('/')
    
    # Discover all categories
    print(f"Discovering categories under '{parent_path}'...")
    results = discover_categories(min_depth=2, max_depth=10)
    
    # Filter to leaf categories under the parent path
    matching_leaves = []
    for cat in results['leaf_categories']:
        cat_segments = cat['segments']
        
        # Check if this category is under the parent path
        if len(cat_segments) > len(segments):
            # Compare the prefix
            matches = all(
                cat_segments[i].lower() == segments[i].lower()
                for i in range(len(segments))
            )
            if matches:
                matching_leaves.append(cat)
    
    return matching_leaves


def run_field_discovery_for_category(
    category_key: str,
    category_url: str,
    sample_size: int = 15,
) -> Dict[str, Any]:
    """Run field discovery for a single category.
    
    Returns the discovery results including suggested fields.
    """
    from scrape.discover_fields import discover_category_fields
    
    print(f"\n{'='*60}")
    print(f"FIELD DISCOVERY: {category_key}")
    print(f"{'='*60}")
    
    # We need to temporarily add this category to CATEGORY_URLS for discovery
    # The discover_fields module uses CATEGORY_URLS
    original_urls = CATEGORY_URLS.copy()
    
    try:
        # Add the category temporarily
        CATEGORY_URLS[category_key] = category_url
        
        results = discover_category_fields(
            category_key,
            sample_size=sample_size,
            min_frequency=0.3,
            max_pages=3,
        )
        return results
    finally:
        # Restore original
        CATEGORY_URLS.clear()
        CATEGORY_URLS.update(original_urls)


def scrape_dynamic_category(
    category_key: str,
    category_url: str,
    db_path: str,
    max_pages: int,
    force_refresh: bool,
    existing_urls: Set[str],
) -> List[Product]:
    """Scrape a dynamically discovered category."""
    print(f"\n{'='*60}")
    print(f"SCRAPING: {category_key}")
    print(f"URL: {category_url}")
    print(f"{'='*60}")
    
    products = scrape_category(
        category_key=category_key,
        url=category_url,
        existing_urls=existing_urls,
        force_refresh=force_refresh,
        max_pages=max_pages,
        use_db=True,
        db_path=db_path,
    )
    
    return products


def discover_and_scrape_workflow(
    parent_path: str,
    db_path: str,
    max_pages: int,
    force_refresh: bool,
    skip_field_discovery: bool = False,
    field_sample_size: int = 15,
    dry_run: bool = False,
) -> Optional[Dict[str, Any]]:
    """Main workflow: discover subcategories, run field discovery, then scrape.
    
    Args:
        parent_path: Parent category path (e.g., 'components/drivetrain')
        db_path: Path to SQLite database
        max_pages: Max pages per category
        force_refresh: Whether to re-scrape existing URLs
        skip_field_discovery: Skip field discovery step
        field_sample_size: Sample size for field discovery
        dry_run: Show plan without executing
        
    Returns:
        Summary dict with results, or None if dry_run
    """
    # Step 1: Find leaf categories
    leaf_categories = get_leaf_categories_under_path(parent_path)
    
    if not leaf_categories:
        print(f"\nNo leaf categories found under '{parent_path}'")
        print("Try a different path like 'components/drivetrain' or 'accessories/lighting'")
        return None
    
    print(f"\n{'='*60}")
    print(f"DISCOVER & SCRAPE WORKFLOW")
    print(f"{'='*60}")
    print(f"Parent path: {parent_path}")
    print(f"Leaf categories found: {len(leaf_categories)}")
    print()
    
    for i, cat in enumerate(leaf_categories, 1):
        print(f"  {i}. {cat['key']}: {cat['url']}")
    
    if dry_run:
        print("\n[DRY RUN] Would discover fields and scrape the above categories.")
        print("Remove --dry-run to execute.")
        return None
    
    # Initialize database
    init_db(db_path)
    existing_urls = set() if force_refresh else get_existing_urls(db_path)
    
    # Step 2: Field discovery for each category
    field_results: Dict[str, Dict] = {}
    if not skip_field_discovery:
        print(f"\n{'#'*60}")
        print("PHASE 1: FIELD DISCOVERY")
        print(f"{'#'*60}")
        
        for cat in leaf_categories:
            try:
                results = run_field_discovery_for_category(
                    cat['key'],
                    cat['url'],
                    sample_size=field_sample_size,
                )
                field_results[cat['key']] = results
                
                # Show summary
                if results and results.get('suggested_fields'):
                    print(f"\n  → Found {len(results['suggested_fields'])} common fields")
                    for field in results['suggested_fields'][:5]:
                        print(f"     - {field['label']} ({field['frequency']:.0%})")
            except Exception as e:
                print(f"  ERROR during field discovery: {e}")
    
    # Step 3: Scrape each category
    print(f"\n{'#'*60}")
    print("PHASE 2: SCRAPING")
    print(f"{'#'*60}")
    
    total_products = 0
    for cat in leaf_categories:
        try:
            products = scrape_dynamic_category(
                category_key=cat['key'],
                category_url=cat['url'],
                db_path=db_path,
                max_pages=max_pages,
                force_refresh=force_refresh,
                existing_urls=existing_urls,
            )
            
            # Update existing URLs for next category
            for p in products:
                existing_urls.add(p.url)
            
            total_products += len(products)
            print(f"  → Scraped {len(products)} products from {cat['key']}")
            
        except Exception as e:
            print(f"  ERROR scraping {cat['key']}: {e}")
    
    # Summary
    print(f"\n{'='*60}")
    print("WORKFLOW COMPLETE")
    print(f"{'='*60}")
    print(f"Categories processed: {len(leaf_categories)}")
    print(f"Total products scraped: {total_products}")
    print(f"Database: {db_path}")
    
    # Save field discovery results if any
    results_path = None
    if field_results:
        results_path = f"data/field_discovery_{parent_path.replace('/', '_')}.json"
        Path(results_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Make JSON serializable
        serializable_results = {}
        for key, res in field_results.items():
            if res:
                serializable_results[key] = {
                    'category': res.get('category'),
                    'products_sampled': res.get('products_sampled'),
                    'suggested_fields': res.get('suggested_fields', []),
                    'suggested_config': res.get('suggested_config'),
                }
        
        with open(results_path, 'w') as f:
            json.dump(serializable_results, f, indent=2, ensure_ascii=False)
        print(f"Field discovery results saved to: {results_path}")
    
    return {
        'categories_processed': len(leaf_categories),
        'total_products': total_products,
        'field_results_path': results_path,
    }
