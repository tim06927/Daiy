import time
import random
import csv
import json
import re
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Iterable, List

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.bike-components.de"

# Limit yourself to a small, clearly defined scope for now
CATEGORY_URLS: Dict[str, str] = {
    "cassettes": "https://www.bike-components.de/en/components/drivetrain/cassettes/",
    "chains": "https://www.bike-components.de/en/components/drivetrain/chains/",
    "drivetrain_tools": "https://www.bike-components.de/en/tools-maintenance/tools-by-category/drivetrains/",
    "mtb_gloves": "https://www.bike-components.de/en/apparel/mountain-bike-apparel/gloves/",
}

HEADERS = {
    "User-Agent": "daiy.de educational scraper (contact: mail@timklausmann.de)",
}

# Product URLs look like /en/Brand/Product-Name-p12345/
PRODUCT_URL_RE = re.compile(r"^/en/[^/]+/.+?-p\d+/?$")


@dataclass
class Product:
    category: str
    name: str
    url: str
    brand: Optional[str] = None
    price_text: Optional[str] = None
    sku: Optional[str] = None
    breadcrumbs: Optional[str] = None

    # Text + raw specs
    description: Optional[str] = None
    specs: Optional[Dict[str, str]] = None

    # Normalised chain fields (only filled for category == "chains")
    chain_application: Optional[str] = None
    chain_gearing: Optional[str] = None
    chain_num_links: Optional[str] = None
    chain_closure_type: Optional[str] = None
    chain_pin_type: Optional[str] = None
    chain_directional: Optional[str] = None
    chain_material: Optional[str] = None


def fetch_html(url: str) -> str:
    """Polite HTTP GET with basic error handling and random sleep."""
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    time.sleep(random.uniform(1.0, 3.0))  # polite delay
    return resp.text


def parse_category_page_for_product_links(html: str) -> List[str]:
    """
    Extract product detail URLs from a category page.

    We only accept links that look like /en/Brand/Product-Name-p12345/
    to avoid menu/category links.
    """
    soup = BeautifulSoup(html, "html.parser")
    product_links: List[str] = []

    for a in soup.select("a[href^='/en/']"):
        href = a.get("href")
        if not href:
            continue
        if PRODUCT_URL_RE.match(href):
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


def extract_sku(soup: BeautifulSoup) -> Optional[str]:
    """Extract item number / SKU from the product page."""
    # Primary pattern: "Item number: <span>929</span>"
    pid = soup.select_one("div.product-id span")
    if pid:
        text = pid.get_text(strip=True)
        if text:
            return text

    # Fallback: search in dt/th
    for label in soup.find_all(["dt", "th"]):
        label_text = label.get_text(strip=True).lower()
        if "item number" in label_text or "article number" in label_text or "art. no" in label_text:
            value_el = label.find_next(["dd", "td"])
            if value_el:
                return value_el.get_text(strip=True)
    return None


def extract_breadcrumbs(soup: BeautifulSoup) -> Optional[str]:
    """Try to extract breadcrumbs as a 'A > B > C' string (optional)."""
    nav = soup.find("nav", attrs={"aria-label": "breadcrumb"})
    if not nav:
        return None
    parts = [el.get_text(strip=True) for el in nav.find_all(["a", "span"]) if el.get_text(strip=True)]
    return " > ".join(parts) if parts else None


def extract_description_and_specs(soup: BeautifulSoup) -> tuple[Optional[str], Dict[str, str]]:
    """
    Extract the full description text and all specs (dt/dd pairs)
    from the Product Description block.
    """
    desc_container = soup.select_one(
        'div.description[data-overlay="product-description"] div.site-text'
    )
    if not desc_container:
        return None, {}

    # Full description as plain text (you can keep HTML if you prefer)
    description_text = " ".join(desc_container.stripped_strings)

    # Specs from all <dl><dt><dd>
    specs: Dict[str, str] = {}
    for dl in desc_container.find_all("dl"):
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            key = dt.get_text(strip=True).rstrip(":")
            value = " ".join(dd.stripped_strings)
            if key and value:
                specs[key] = value

    return description_text, specs


def pick_spec(specs: Dict[str, str], keys: List[str]) -> Optional[str]:
    """Pick a spec value by trying a list of possible labels (case-insensitive)."""
    # Exact matches first
    for k in keys:
        if k in specs:
            return specs[k]

    # Case-insensitive fallback
    lower_map = {kk.lower(): vv for kk, vv in specs.items()}
    for k in keys:
        if k.lower() in lower_map:
            return lower_map[k.lower()]
    return None


def map_chain_specs(category_key: str, specs: Dict[str, str]) -> Dict[str, Optional[str]]:
    """Map raw specs dict into normalised chain_* fields if this is a chain."""
    if category_key != "chains" or not specs:
        return {
            "chain_application": None,
            "chain_gearing": None,
            "chain_num_links": None,
            "chain_closure_type": None,
            "chain_pin_type": None,
            "chain_directional": None,
            "chain_material": None,
        }

    return {
        "chain_application": pick_spec(specs, ["Application", "Einsatzbereich"]),
        "chain_gearing": pick_spec(specs, ["Gearing", "Schaltstufen hinten", "Speed"]),
        "chain_num_links": pick_spec(specs, ["Number of Links", "Kettenlänge", "Links"]),
        "chain_closure_type": pick_spec(specs, ["Closure Type", "Verschlussart"]),
        "chain_pin_type": pick_spec(specs, ["Pin Type", "Nietentyp"]),
        "chain_directional": pick_spec(specs, ["Directional", "Laufrichtungsgebunden"]),
        "chain_material": pick_spec(specs, ["Material"]),
    }


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

    # Chain-specific mappings
    chain_fields = map_chain_specs(category_key, specs)

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
    print(f"Scraping category {category_key}: {url}")
    html = fetch_html(url)

    product_links = parse_category_page_for_product_links(html)
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


def save_products_to_csv(products: Iterable[Product], path: str) -> None:
    products_list = list(products)
    if not products_list:
        print("No products to save.")
        return

    fieldnames = list(asdict(products_list[0]).keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in products_list:
            row = asdict(p)
            # specs is a dict → serialise to JSON
            if row.get("specs") is not None:
                row["specs"] = json.dumps(row["specs"], ensure_ascii=False)
            writer.writerow(row)

    print(f"Saved {len(products_list)} products to {path}")


def main() -> None:
    all_products: List[Product] = []
    for category_key, url in CATEGORY_URLS.items():
        products = scrape_category(category_key, url)
        all_products.extend(products)

    save_products_to_csv(all_products, "bc_products_sample.csv")


if __name__ == "__main__":
    main()
