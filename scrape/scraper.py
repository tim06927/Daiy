"""Core scraping logic."""

import random
import time
from typing import List, Optional, Set

import requests  # type: ignore[import-untyped]
from bs4 import BeautifulSoup

__all__ = [
    "fetch_html",
    "extract_product_links",
    "parse_product_page",
    "scrape_category",
    "save_product_to_db",
]

from scrape.config import (
    BASE_URL,
    DB_PATH,
    DEFAULT_MAX_PAGES,
    DELAY_MAX,
    DELAY_MIN,
    HEADERS,
    REQUEST_TIMEOUT,
    get_spec_config,
)
from scrape.db import (
    get_existing_urls,
    get_spec_table_for_category,
    init_db,
    update_scrape_state,
    upsert_category_specs,
    upsert_product,
)
from scrape.html_utils import (
    extract_breadcrumbs,
    extract_current_page,
    extract_description_and_specs,
    extract_next_page_url,
    extract_primary_image_url,
    extract_sku,
    extract_total_pages,
    is_product_url,
    map_category_specs,
)
from scrape.models import Product


def fetch_html(url: str) -> str:
    """Polite HTTP GET with basic error handling and random sleep."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise ValueError(
            f"Invalid URL in scrape/config.py: {url}\n"
            f"HTTP Error {e.response.status_code}: {e.response.reason}\n"
            f"Please verify the URL is correct and accessible."
        ) from e
    except requests.exceptions.RequestException as e:
        raise ValueError(
            f"Failed to fetch {url}: {e}\n"
            f"Please check your internet connection and the URL in scrape/config.py"
        ) from e
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))  # polite delay
    return str(resp.text)


def extract_product_links(html: str) -> List[str]:
    """
    Extract product detail URLs from a category page.

    Only accepts links that look like /en/Brand/Product-Name-p12345/
    to avoid menu/category links.
    """
    soup = BeautifulSoup(html, "html.parser")
    product_links: List[str] = []

    for a in soup.select("a[href^='/en/']"):
        href = a.get("href")
        if not href or not isinstance(href, str):
            continue
        if is_product_url(href):
            full_url = BASE_URL + href
            product_links.append(full_url)

    # de-duplicate while preserving order
    seen = set()
    unique_links: List[str] = []
    for link in product_links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)

    return unique_links


def parse_product_page(category_key: str, html: str, url: str) -> Product:
    """Parse a single product page into a Product object."""
    soup = BeautifulSoup(html, "html.parser")

    # Name
    name_el = soup.select_one('h1[data-test="auto-product-name"]') or soup.find("h1")
    name = name_el.get_text(strip=True) if name_el else ""

    # Brand: from manufacturer block if present, else first word of title
    brand: Optional[str] = None
    brand_img = soup.select_one(".manufacturer img[alt]")
    if brand_img:
        alt_val = brand_img.get("alt")
        if alt_val and isinstance(alt_val, str):
            brand = alt_val.strip()
    if brand is None and name:
        brand = name.split()[0]

    # Price
    price_el = soup.select_one('[data-test="product-price"]')
    price_text: Optional[str] = None
    if price_el is not None:
        price_text = price_el.get_text(strip=True)
    else:
        # fallback: any string containing €
        price_str = soup.find(string=lambda t: t and "€" in t)
        price_text = price_str.strip() if isinstance(price_str, str) else None

    # SKU & breadcrumbs
    sku = extract_sku(soup)
    breadcrumbs_text = extract_breadcrumbs(soup)

    # Description + specs + image
    description, specs = extract_description_and_specs(soup)
    image_url = extract_primary_image_url(soup)

    # Category-specific spec mapping using the registry
    category_specs = map_category_specs(category_key, specs) if specs else {}

    return Product(
        category=category_key,
        name=name,
        url=url,
        brand=brand,
        price_text=price_text,
        image_url=image_url,
        sku=sku,
        breadcrumbs=breadcrumbs_text,
        description=description,
        specs=specs or None,
        category_specs=category_specs,
    )


def scrape_category(
    category_key: str,
    url: str,
    existing_urls: Optional[Set[str]] = None,
    force_refresh: bool = False,
    max_pages: int = DEFAULT_MAX_PAGES,
    use_db: bool = True,
    db_path: str = DB_PATH,
) -> List[Product]:
    """Scrape all products from a category, handling pagination.

    Args:
        category_key: The category identifier (e.g., 'chains', 'cassettes')
        url: The base category URL
        existing_urls: Set of URLs to skip (for incremental scraping)
        force_refresh: If True, re-scrape even existing URLs
        max_pages: Maximum number of pages to scrape (safety limit)
        use_db: If True, save products to SQLite database
        db_path: Path to the SQLite database

    Returns:
        List of Product objects scraped
    """
    print(f"Scraping category {category_key}: {url}")
    
    if use_db:
        init_db(db_path)
    
    products: List[Product] = []
    seen_urls = existing_urls if existing_urls is not None else set()
    
    current_url = url
    page_num = 0
    total_pages: Optional[int] = None
    
    while current_url and page_num < max_pages:
        page_num += 1
        print(f"  Page {page_num}" + (f"/{total_pages}" if total_pages else "") + f": {current_url}")
        
        html = fetch_html(current_url)
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract pagination info on first page
        if page_num == 1:
            total_pages = extract_total_pages(soup)
            if total_pages:
                print(f"  Found {total_pages} total pages")
        
        # Extract product links from this page
        product_links = extract_product_links(html)
        print(f"    Found {len(product_links)} product links on page {page_num}")
        
        # Scrape each product
        for i, product_url in enumerate(product_links, start=1):
            if not force_refresh and product_url in seen_urls:
                print(f"      [{i}/{len(product_links)}] SKIP (already scraped): {product_url}")
                continue

            print(f"      [{i}/{len(product_links)}] {product_url}")
            try:
                product_html = fetch_html(product_url)
                product = parse_product_page(category_key, product_html, product_url)
                products.append(product)
                seen_urls.add(product_url)
                
                # Save to database immediately
                if use_db:
                    save_product_to_db(product, db_path)
                    
            except Exception as e:
                print(f"        ERROR fetching/parsing {product_url}: {e}")
        
        # Update scrape state after each page
        if use_db:
            update_scrape_state(db_path, category_key, page_num, total_pages)
        
        # Get next page URL
        next_url = extract_next_page_url(soup, current_url)
        if next_url and next_url != current_url:
            current_url = next_url
        else:
            current_url = None  # type: ignore
            print(f"  No more pages found after page {page_num}")
    
    if page_num >= max_pages:
        print(f"  Reached max pages limit ({max_pages})")
    
    print(f"  Category {category_key} complete: {len(products)} new products scraped")
    return products


def save_product_to_db(product: Product, db_path: str = DB_PATH) -> None:
    """Save a single product to the database."""
    # Save core product data
    product_id = upsert_product(
        db_path=db_path,
        category=product.category,
        name=product.name,
        url=product.url,
        image_url=product.image_url,
        brand=product.brand,
        price_text=product.price_text,
        sku=product.sku,
        breadcrumbs=product.breadcrumbs,
        description=product.description,
        specs=product.specs,
    )
    product.id = product_id
    
    # Save category-specific specs
    if product.category_specs:
        spec_table = get_spec_table_for_category(product.category)
        if spec_table:
            upsert_category_specs(db_path, spec_table, product_id, product.category_specs)
