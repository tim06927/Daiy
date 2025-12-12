"""HTML parsing and extraction utilities."""

import re
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

# Product URLs look like /en/Brand/Product-Name-p12345/
PRODUCT_URL_RE = re.compile(r"^/en/[^/]+/.+?-p\d+/?$")


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
    parts = [
        el.get_text(strip=True) for el in nav.find_all(["a", "span"]) if el.get_text(strip=True)
    ]
    return " > ".join(parts) if parts else None


def extract_description_and_specs(soup: BeautifulSoup) -> Tuple[Optional[str], Dict[str, str]]:
    """
    Extract the full description text and all specs (dt/dd pairs)
    from the Product Description block.
    """
    desc_container = soup.select_one(
        'div.description[data-overlay="product-description"] div.site-text'
    )
    if not desc_container:
        return None, {}

    # Full description as plain text
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


def extract_primary_image_url(soup: BeautifulSoup) -> Optional[str]:
    """Extract the first product image URL (thumbnail/primary) from the page."""
    # Try dedicated image container
    img = soup.select_one('div.product-media img[src]')
    if img and img.get("src"):
        return img.get("src")

    # Fallback: any img with data-test or alt near product
    fallback_img = soup.find("img", src=True)
    if fallback_img:
        return fallback_img.get("src")
    return None


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


def map_chain_specs(specs: Dict[str, str]) -> Dict[str, Optional[str]]:
    """Map raw specs dict into normalised chain_* fields."""
    if not specs:
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


def is_product_url(href: str) -> bool:
    """Check if a URL looks like a product detail page."""
    return PRODUCT_URL_RE.match(href) is not None
