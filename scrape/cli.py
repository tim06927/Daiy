"""Command-line interface for the scraper."""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

# Add parent directory to path to allow imports when run as script
sys.path.insert(0, str(Path(__file__).parent.parent))

__all__ = ["main", "scrape_all", "parse_args", "show_stats"]

from scrape.config import (
    CATEGORY_URLS,
    DB_PATH,
    DEFAULT_MAX_PAGES,
    MAX_PAGES_PER_CATEGORY,
    OUTPUT_PATH,
)
from scrape.csv_utils import (
    export_category_to_csv,
    export_db_to_csv,
    load_existing_products,
    save_products_to_csv,
)
from scrape.db import get_existing_urls, get_product_count, init_db
from scrape.models import Product
from scrape.scraper import scrape_category
from scrape.workflows import discover_and_scrape_workflow


def scrape_all(
    existing_urls: Set[str],
    force_refresh: bool,
    max_pages: int = DEFAULT_MAX_PAGES,
    use_db: bool = True,
    db_path: str = DB_PATH,
    categories: Optional[List[str]] = None,
) -> List[Product]:
    """Scrape all configured categories and return new products.
    
    Args:
        existing_urls: Set of URLs to skip
        force_refresh: If True, re-scrape existing URLs
        max_pages: Maximum pages per category
        use_db: Whether to save to SQLite
        db_path: Path to SQLite database
        categories: Optional list of categories to scrape (default: all)
    """
    all_products: List[Product] = []

    # Filter categories if specified
    urls_to_scrape = CATEGORY_URLS
    if categories:
        urls_to_scrape = {k: v for k, v in CATEGORY_URLS.items() if k in categories}
        if not urls_to_scrape:
            print(f"Warning: No valid categories found. Available: {list(CATEGORY_URLS.keys())}")
            return []

    for category_key, url in urls_to_scrape.items():
        products = scrape_category(
            category_key,
            url,
            existing_urls=existing_urls,
            force_refresh=force_refresh,
            max_pages=max_pages,
            use_db=use_db,
            db_path=db_path,
        )
        # Update the shared set so later categories also skip duplicates
        for p in products:
            existing_urls.add(p.url)
        all_products.extend(products)
    return all_products


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bike-components scraper with pagination and SQLite storage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape all categories (incremental, max 3 pages each)
  python -m scrape.cli
  
  # Full refresh of chains category only, up to 10 pages
  python -m scrape.cli --mode full --categories chains --max-pages 10
  
  # Export database to CSV
  python -m scrape.cli --export-csv data/export.csv
  
  # Export only cassettes to their own CSV
  python -m scrape.cli --export-category cassettes --export-csv data/cassettes.csv
  
  # Show database statistics
  python -m scrape.cli --stats
  
  # Discover and scrape all subcategories under "drivetrain"
  python -m scrape.cli --discover-scrape components/drivetrain
  
  # Discover and scrape with field discovery, 5 pages max
  python -m scrape.cli --discover-scrape accessories/lighting --max-pages 5
        """,
    )

    # Scraping mode
    parser.add_argument(
        "--mode",
        choices=["incremental", "full"],
        default="incremental",
        help="incremental: skip URLs already scraped (default); full: rescrape everything",
    )

    # Pagination
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help=f"Maximum pages to scrape per category (default: {DEFAULT_MAX_PAGES}, max: {MAX_PAGES_PER_CATEGORY})",
    )

    # Category selection
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=list(CATEGORY_URLS.keys()),
        help=f"Categories to scrape (default: all). Choices: {list(CATEGORY_URLS.keys())}",
    )

    # Database options
    parser.add_argument(
        "--db",
        default=DB_PATH,
        help=f"SQLite database path (default: {DB_PATH})",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Don't save to database (legacy CSV-only mode)",
    )

    # CSV output
    parser.add_argument(
        "--output",
        default=OUTPUT_PATH,
        help=f"Output CSV path for legacy mode (default: {OUTPUT_PATH})",
    )

    # Export options
    parser.add_argument(
        "--export-csv",
        metavar="PATH",
        help="Export database to CSV file",
    )
    parser.add_argument(
        "--export-category",
        metavar="CATEGORY",
        choices=list(CATEGORY_URLS.keys()),
        help="Export only this category (use with --export-csv)",
    )

    # Info commands
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show database statistics and exit",
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List available categories and exit",
    )

    # Discover and scrape workflow
    parser.add_argument(
        "--discover-scrape",
        metavar="PARENT_PATH",
        help="Discover leaf subcategories under a parent path, run field discovery, then scrape. "
             "Example: 'components/drivetrain' or 'accessories/lighting'",
    )
    parser.add_argument(
        "--skip-field-discovery",
        action="store_true",
        help="Skip field discovery step in --discover-scrape (use existing config)",
    )
    parser.add_argument(
        "--field-sample-size",
        type=int,
        default=15,
        help="Number of products to sample for field discovery (default: 15)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be scraped without actually scraping",
    )

    return parser.parse_args()


def show_stats(db_path: str) -> None:
    """Display database statistics."""
    from scrape.db import get_connection, get_product_count

    init_db(db_path)

    print(f"\n{'='*50}")
    print(f"Database: {db_path}")
    print(f"{'='*50}")

    total = get_product_count(db_path)
    print(f"\nTotal products: {total}")

    print("\nProducts by category:")
    for category in CATEGORY_URLS.keys():
        count = get_product_count(db_path, category=category)
        print(f"  {category}: {count}")

    # Show scrape state
    print("\nScrape state:")
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scrape_state ORDER BY category")
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"  {row['category']}: page {row['last_page_scraped']}"
                      f" (of {row['total_pages_found'] or '?'})"
                      f" - last scraped: {row['last_scraped_at'] or 'never'}")
        else:
            print("  No scraping history yet")

    print()


def main() -> None:
    """Main entry point for CLI."""
    args = parse_args()

    # Handle info commands
    if args.list_categories:
        print("Available categories:")
        for key, url in CATEGORY_URLS.items():
            print(f"  {key}: {url}")
        return

    if args.stats:
        show_stats(args.db)
        return

    # Handle export commands
    if args.export_csv:
        init_db(args.db)
        if args.export_category:
            export_category_to_csv(args.db, args.export_category, args.export_csv)
        else:
            export_db_to_csv(args.db, args.export_csv)
        return

    # Handle discover-and-scrape workflow
    if args.discover_scrape:
        discover_and_scrape_workflow(
            parent_path=args.discover_scrape,
            db_path=args.db,
            max_pages=min(args.max_pages, MAX_PAGES_PER_CATEGORY),
            force_refresh=(args.mode == "full"),
            skip_field_discovery=args.skip_field_discovery,
            field_sample_size=args.field_sample_size,
            dry_run=args.dry_run,
        )
        return

    # Main scraping flow (original behavior)
    force_refresh = args.mode == "full"
    use_db = not args.no_db
    max_pages = min(args.max_pages, MAX_PAGES_PER_CATEGORY)

    existing_rows: List[Dict[str, str]] = []
    existing_fieldnames: List[str] = []
    existing_urls: Set[str] = set()

    if not force_refresh:
        if use_db:
            # Get existing URLs from database
            init_db(args.db)
            existing_urls = get_existing_urls(args.db)
            print(f"Found {len(existing_urls)} existing products in database")
        else:
            # Legacy: get from CSV
            existing_rows, existing_fieldnames = load_existing_products(args.output)
            existing_urls = {row["url"] for row in existing_rows if "url" in row and row["url"]}

    new_products = scrape_all(
        existing_urls,
        force_refresh,
        max_pages=max_pages,
        use_db=use_db,
        db_path=args.db,
        categories=args.categories,
    )

    # Save to CSV if using legacy mode or explicitly requested
    if not use_db:
        save_products_to_csv(
            new_products,
            args.output,
            existing_rows=None if force_refresh else existing_rows,
            fieldnames=existing_fieldnames,
        )
    else:
        print(f"\nProducts saved to database: {args.db}")
        print(f"Total products in database: {get_product_count(args.db)}")
        print("\nTo export to CSV, run:")
        print(f"  python -m scrape.cli --export-csv {args.output}")


if __name__ == "__main__":
    main()
