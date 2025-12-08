"""Core scraping logic."""

import time
import random
from typing import List

import requests
from bs4 import BeautifulSoup

from scrape.config import BASE_URL, HEADERS, REQUEST_TIMEOUT, DELAY_MIN, DELAY_MAX
from scrape.models import Product
from scrape.html_utils import (
    extract_sku,
    extract_breadcrumbs,
    extract_description_and_specs,
    is_product_url,
    map_chain_specs,
)


def fetch_html(url: str) -> str:
    """Polite HTTP GET with basic error handling and random sleep."""
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))  # polite delay
    return resp.text


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
        if not href:
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
    brand = None
    brand_img = soup.select_one(".manufacturer img[alt]")
    if brand_img and brand_img.get("alt"):
        brand = brand_img["alt"].strip()
    elif name:
        brand = name.split()[0]

    # Price
    price_el = soup.select_one('[data-test="product-price"]')
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


def scrape_category(category_key: str, url: str) -> List[Product]:
    """Scrape all products from a category page."""
    print(f"Scraping category {category_key}: {url}")
    html = fetch_html(url)

    product_links = extract_product_links(html)
    print(f"  Found {len(product_links)} product links on first page")

    # NOTE: For a PoC we only scrape the first page.
    # To add pagination later, inspect the "next page" link and loop.

    products: List[Product] = []
    for i, product_url in enumerate(product_links, start=1):
        print(f"    [{i}/{len(product_links)}] {product_url}")
        try:
            product_html = fetch_html(product_url)
            product = parse_product_page(category_key, product_html, product_url)
            products.append(product)
        except Exception as e:
            print(f"      ERROR fetching/parsing {product_url}: {e}")
    return products
