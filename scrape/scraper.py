"""Core scraping logic."""

import random
import time
from typing import Any, Dict, List, Optional, Set

import requests  # type: ignore[import-untyped]
from bs4 import BeautifulSoup

__all__ = [
    "fetch_html",
    "extract_product_links",
    "parse_product_page",
    "scrape_category",
    "save_product_to_db",
    "create_session",
]

from scrape.config import (
    BASE_URL,
    DB_PATH,
    DEFAULT_MAX_PAGES,
    DELAY_MAX,
    DELAY_MIN,
    DELAY_OVERNIGHT_MAX,
    DELAY_OVERNIGHT_MIN,
    HEADERS,
    MAX_RETRIES,
    MAX_RETRY_BACKOFF,
    REQUEST_TIMEOUT,
    RETRY_BACKOFF_BASE,
    RETRY_STATUS_CODES,
)
from scrape.db import (
    add_product_category,
    get_discovered_fields,
    get_spec_table_for_category,
    init_db,
    update_scrape_state,
    upsert_category_specs,
    upsert_dynamic_specs,
    upsert_product,
)
from scrape.html_utils import (
    extract_breadcrumbs,
    extract_description_and_specs,
    extract_next_page_url,
    extract_primary_image_url,
    extract_sku,
    extract_total_pages,
    is_product_url,
    map_category_specs,
    map_dynamic_specs,
)
from scrape.logging_config import get_logger, log_scrape_event
from scrape.models import Product
from scrape.shutdown import shutdown_requested
from scrape.url_validation import (
    URLValidationError,
    sanitize_url,
    validate_image_url,
    validate_url,
)

# Get logger for this module
logger = get_logger("scraper")


# Module-level session for connection reuse
_session: Optional[requests.Session] = None


def create_session() -> requests.Session:
    """Create a requests Session with connection pooling and proper headers.
    
    Using a session provides:
    - Connection reuse (keep-alive) - reduces server load
    - Cookie persistence across requests
    - Gzip/deflate compression (enabled by default)
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    # Accept compressed responses to reduce bandwidth
    session.headers.setdefault("Accept-Encoding", "gzip, deflate")
    return session


def _get_session() -> requests.Session:
    """Get or create the module-level session."""
    global _session
    if _session is None:
        _session = create_session()
    return _session


def fetch_html(
    url: str,
    delay_min: float = DELAY_MIN,
    delay_max: float = DELAY_MAX,
    session: Optional[requests.Session] = None,
) -> str:
    """Polite HTTP GET with exponential backoff retry and random sleep.
    
    Args:
        url: URL to fetch
        delay_min: Minimum delay after request (seconds)
        delay_max: Maximum delay after request (seconds)
        session: Optional requests.Session for connection reuse
        
    Returns:
        HTML content as string
        
    Raises:
        ValueError: If URL is invalid or request fails after all retries
    """
    # Validate URL before fetching
    try:
        url = validate_url(url)
    except URLValidationError as e:
        logger.error(f"URL validation failed: {e}")
        raise ValueError(f"Invalid URL: {e}") from e
    
    sess = session or _get_session()
    last_exception: Optional[Exception] = None
    
    for attempt in range(MAX_RETRIES + 1):
        # Check for shutdown request
        if shutdown_requested():
            logger.info("Shutdown requested, stopping fetch")
            raise KeyboardInterrupt("Graceful shutdown requested")
        
        try:
            resp = sess.get(url, timeout=REQUEST_TIMEOUT)
            
            # Check if we should retry based on status code
            if resp.status_code in RETRY_STATUS_CODES:
                if attempt < MAX_RETRIES:
                    backoff = min(RETRY_BACKOFF_BASE ** attempt, MAX_RETRY_BACKOFF) + random.uniform(0, 1)
                    logger.warning(
                        f"Received {resp.status_code}, backing off {backoff:.1f}s "
                        f"(attempt {attempt + 1}/{MAX_RETRIES})"
                    )
                    time.sleep(backoff)
                    continue
            
            # For non-retryable status codes or exhausted retries, raise immediately
            resp.raise_for_status()
            
            # Success - apply polite delay before returning
            time.sleep(random.uniform(delay_min, delay_max))
            return str(resp.text)
            
        except requests.exceptions.HTTPError as e:
            last_exception = e
            logger.error(f"HTTP error fetching {url}: {e}")
            status_code = e.response.status_code if e.response else "unknown"
            reason = e.response.reason if e.response else "unknown"
            raise ValueError(
                f"HTTP Error {status_code}: {reason}\n"
                f"Failed to fetch: {url}\n"
                f"Please verify the URL is correct and accessible."
            ) from e
            
        except requests.exceptions.ConnectionError as e:
            last_exception = e
            if attempt < MAX_RETRIES:
                backoff = min(RETRY_BACKOFF_BASE ** attempt, MAX_RETRY_BACKOFF) + random.uniform(0, 1)
                logger.warning(
                    f"Connection error, backing off {backoff:.1f}s "
                    f"(attempt {attempt + 1}/{MAX_RETRIES})"
                )
                time.sleep(backoff)
                continue
            logger.error(f"Connection error fetching {url}: {e}")
            raise ValueError(
                f"Failed to fetch {url}: {e}\n"
                f"Please check your internet connection and verify the URL is accessible."
            ) from e
            
        except requests.exceptions.Timeout as e:
            last_exception = e
            if attempt < MAX_RETRIES:
                backoff = min(RETRY_BACKOFF_BASE ** attempt, MAX_RETRY_BACKOFF) + random.uniform(0, 1)
                logger.warning(
                    f"Timeout, backing off {backoff:.1f}s "
                    f"(attempt {attempt + 1}/{MAX_RETRIES})"
                )
                time.sleep(backoff)
                continue
            logger.error(f"Timeout fetching {url}: {e}")
            raise ValueError(
                f"Timeout fetching {url}: {e}\n"
                f"The server may be overloaded. Try again later or increase REQUEST_TIMEOUT."
            ) from e
            
        except requests.exceptions.RequestException as e:
            # Other request errors - don't retry
            logger.error(f"Request error fetching {url}: {e}")
            raise ValueError(
                f"Failed to fetch {url}: {e}\n"
                f"Please check your internet connection and verify the URL is accessible."
            ) from e
    
    # Should not reach here, but just in case
    logger.error(f"Failed to fetch {url} after {MAX_RETRIES} retries")
    raise ValueError(f"Failed to fetch {url} after {MAX_RETRIES} retries") from last_exception


def extract_product_links(html: str) -> List[str]:
    """
    Extract product detail URLs from a category page.

    Only accepts links that look like /en/Brand/Product-Name-p12345/
    to avoid menu/category links. Validates all URLs before returning.
    """
    soup = BeautifulSoup(html, "html.parser")
    product_links: List[str] = []

    for a in soup.select("a[href^='/en/']"):
        href = a.get("href")
        if not href or not isinstance(href, str):
            continue
        if is_product_url(href):
            full_url = BASE_URL + href
            # Validate the URL
            try:
                validated_url = validate_url(full_url)
                product_links.append(validated_url)
            except URLValidationError as e:
                logger.warning(f"Skipping invalid product URL: {full_url} - {e}")
                continue

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
    raw_image_url = extract_primary_image_url(soup)
    
    # Validate and sanitize image URL
    image_url: Optional[str] = None
    if raw_image_url:
        try:
            image_url = validate_image_url(raw_image_url)
        except URLValidationError as e:
            logger.warning(f"Invalid image URL for {url}: {e}")
            image_url = None

    # Category-specific spec mapping using the registry (legacy hardcoded)
    category_specs = map_category_specs(category_key, specs) if specs else {}

    return Product(
        category=category_key,
        name=name,
        url=sanitize_url(url),
        brand=brand,
        price_text=price_text,
        image_url=image_url,
        sku=sku,
        breadcrumbs=breadcrumbs_text,
        description=description,
        specs=specs or None,
        category_specs=category_specs,
    )


def scrape_product(
    category_key: str,
    url: str,
    discovered_fields: Optional[List[Dict[str, Any]]] = None,
) -> Product:
    """Fetch and parse a single product.
    
    Args:
        category_key: Category identifier.
        url: Product URL.
        discovered_fields: Optional list of discovered field mappings for this category.
            If provided, these will be used to create dynamic_specs on the Product.
            
    Returns:
        Product object with specs populated.
    """
    html = fetch_html(url)
    product = parse_product_page(category_key, html, url)
    
    # If we have discovered fields, also populate dynamic_specs
    if discovered_fields and product.specs:
        product.dynamic_specs = map_dynamic_specs(product.specs, discovered_fields)
    
    return product


def scrape_category(
    category_key: str,
    url: str,
    existing_urls: Optional[Set[str]] = None,
    force_refresh: bool = False,
    max_pages: int = DEFAULT_MAX_PAGES,
    use_db: bool = True,
    db_path: str = DB_PATH,
    overnight: bool = False,
    discovered_fields: Optional[List[Dict[str, Any]]] = None,
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
        overnight: If True, use longer delays between requests
        discovered_fields: List of discovered field mappings for this category.
            If provided, these will be used to normalize specs into dynamic_specs.

    Returns:
        List of Product objects scraped
    """
    # Select delay settings based on mode
    if overnight:
        delay_min, delay_max = DELAY_OVERNIGHT_MIN, DELAY_OVERNIGHT_MAX
        logger.info(
            f"Scraping category {category_key} (overnight mode: {delay_min}-{delay_max}s delays): {url}"
        )
    else:
        delay_min, delay_max = DELAY_MIN, DELAY_MAX
        logger.info(f"Scraping category {category_key}: {url}")
    
    # Log scrape start event
    log_scrape_event("category_start", {
        "category": category_key,
        "url": url,
        "overnight_mode": overnight,
        "max_pages": max_pages,
        "force_refresh": force_refresh,
    })

    if use_db:
        init_db(db_path)

    products: List[Product] = []
    seen_urls = existing_urls if existing_urls is not None else set()

    current_url = url
    page_num = 0
    total_pages: Optional[int] = None
    
    # Track if we were interrupted
    interrupted = False

    try:
        while current_url and page_num < max_pages:
            # Check for shutdown
            if shutdown_requested():
                logger.info("Shutdown requested, stopping category scrape gracefully")
                interrupted = True
                break
            
            page_num += 1
            page_info = f"Page {page_num}" + (f"/{total_pages}" if total_pages else "")
            logger.info(f"  {page_info}: {current_url}")

            html = fetch_html(current_url, delay_min, delay_max)
            soup = BeautifulSoup(html, "html.parser")

            # Extract pagination info on first page
            if page_num == 1:
                total_pages = extract_total_pages(soup)
                if total_pages:
                    logger.info(f"  Found {total_pages} total pages")

            # Extract product links from this page
            product_links = extract_product_links(html)
            logger.info(f"    Found {len(product_links)} product links on page {page_num}")

            # Scrape each product
            for i, product_url in enumerate(product_links, start=1):
                # Check for shutdown between products
                if shutdown_requested():
                    logger.info("Shutdown requested, stopping after current product")
                    interrupted = True
                    break
                
                # Check if product was already scraped (either in this run or previously)
                already_scraped = (not force_refresh) and (product_url in seen_urls or 
                                 (existing_urls is not None and product_url in existing_urls))
                
                if already_scraped:
                    if product_url in seen_urls:
                        logger.debug(f"      [{i}/{len(product_links)}] EXISTING (multi-category, same run): {product_url}")
                    else:
                        logger.debug(f"      [{i}/{len(product_links)}] EXISTING (multi-category, previous run): {product_url}")
                    
                    # Product already scraped - just add category association
                    if use_db:
                        from scrape.db import get_connection, add_product_category
                        with get_connection(db_path) as conn:
                            cursor = conn.cursor()
                            cursor.execute("SELECT id FROM products WHERE url = ?", (product_url,))
                            row = cursor.fetchone()
                            if row:
                                product_id = row[0]
                                add_product_category(db_path, product_id, category_key)
                                logger.debug(f"        Added category '{category_key}' to product ID {product_id}")
                    continue

                logger.info(f"      [{i}/{len(product_links)}] {product_url}")
                try:
                    product_html = fetch_html(product_url, delay_min, delay_max)
                    product = parse_product_page(category_key, product_html, product_url)
                    
                    # If we have discovered fields, populate dynamic_specs
                    if discovered_fields and product.specs:
                        product.dynamic_specs = map_dynamic_specs(product.specs, discovered_fields)
                    
                    products.append(product)
                    seen_urls.add(product_url)

                    # Save to database immediately
                    if use_db:
                        save_product_to_db(product, db_path)

                except KeyboardInterrupt:
                    logger.info("Interrupted during product fetch")
                    interrupted = True
                    break
                except Exception as e:
                    logger.error(f"        ERROR fetching/parsing {product_url}: {e}")
                    log_scrape_event("product_error", {
                        "url": product_url,
                        "error": str(e),
                        "category": category_key,
                    })
            
            if interrupted:
                break

            # Update scrape state after each page
            if use_db:
                update_scrape_state(db_path, category_key, page_num, total_pages)

            # Get next page URL
            next_url = extract_next_page_url(soup, current_url)
            if next_url and next_url != current_url:
                current_url = next_url
            else:
                # No more pages to scrape
                break

        if page_num >= max_pages and not interrupted:
            logger.info(f"  Reached max pages limit ({max_pages})")

    except KeyboardInterrupt:
        logger.info("Category scrape interrupted by user")
        interrupted = True

    # Log completion
    status = "interrupted" if interrupted else "complete"
    logger.info(f"  Category {category_key} {status}: {len(products)} new products scraped")
    log_scrape_event("category_complete", {
        "category": category_key,
        "products_scraped": len(products),
        "pages_scraped": page_num,
        "status": status,
    })
    
    return products


def save_product_to_db(product: Product, db_path: str = DB_PATH) -> None:
    """Save a single product to the database with category association.
    
    This function:
    1. Upserts the product (creates or updates core data)
    2. Adds a category association via junction table
    3. Saves category-specific specs if applicable (legacy system)
    4. Saves dynamic specs if available (new flexible system)
    
    Args:
        product: Product to save
        db_path: Path to database
    """
    # Save core product data (uses URL as unique key)
    product_id = upsert_product(
        db_path=db_path,
        category=product.category,  # Still stored for backward compatibility
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

    # Add category association (idempotent)
    add_product_category(db_path, product_id, product.category)

    # Save category-specific specs (legacy hardcoded tables)
    if product.category_specs:
        spec_table = get_spec_table_for_category(product.category)
        if spec_table:
            upsert_category_specs(db_path, spec_table, product_id, product.category_specs)

    # Save dynamic specs (new flexible system)
    if product.dynamic_specs:
        upsert_dynamic_specs(db_path, product_id, product.category, product.dynamic_specs)
