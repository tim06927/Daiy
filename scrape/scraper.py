"""Core scraping logic."""

import random
import time
from typing import List, Optional, Set

import requests  # type: ignore[import-untyped]
from bs4 import BeautifulSoup

from scrape.config import BASE_URL, DELAY_MAX, DELAY_MIN, HEADERS, REQUEST_TIMEOUT
from scrape.html_utils import (
    extract_breadcrumbs,
    extract_description_and_specs,
    extract_sku,
    is_product_url,
    map_chain_specs,
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

    # Description + specs
    description, specs = extract_description_and_specs(soup)

    # Chain-specific mappings (only for chains category)
    chain_fields = {}
    if category_key == "chains":
        chain_fields = map_chain_specs(specs)
    else:
        chain_fields = {
            "chain_application": None,
            "chain_gearing": None,
            "chain_num_links": None,
            "chain_closure_type": None,
            "chain_pin_type": None,
            "chain_directional": None,
            "chain_material": None,
        }

    return Product(
        category=category_key,
        name=name,
        url=url,
        brand=brand,
        price_text=price_text,
        sku=sku,
        breadcrumbs=breadcrumbs_text,
        description=description,
        specs=specs or None,
        **chain_fields,
    )


def scrape_category(
    category_key: str,
    url: str,
    existing_urls: Optional[Set[str]] = None,
    force_refresh: bool = False,
) -> List[Product]:
    """Scrape all products from a category page.

    If force_refresh is False, any product URLs already present in ``existing_urls``
    are skipped to avoid re-scraping the same items.
    """
    print(f"Scraping category {category_key}: {url}")
    html = fetch_html(url)

    product_links = extract_product_links(html)
    print(f"  Found {len(product_links)} product links on first page")

    # NOTE: For a PoC we only scrape the first page.
    # To add pagination later, inspect the "next page" link and loop.

    products: List[Product] = []
    seen_urls = existing_urls if existing_urls is not None else set()

    for i, product_url in enumerate(product_links, start=1):
        if not force_refresh and product_url in seen_urls:
            print(f"    [{i}/{len(product_links)}] SKIP (already in output): {product_url}")
            continue

        print(f"    [{i}/{len(product_links)}] {product_url}")
        try:
            product_html = fetch_html(product_url)
            product = parse_product_page(category_key, product_html, product_url)
            products.append(product)
            seen_urls.add(product_url)
        except Exception as e:
            print(f"      ERROR fetching/parsing {product_url}: {e}")
    return products
