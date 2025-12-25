"""HTML parsing and extraction utilities."""

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup

from scrape.config import BASE_URL, CATEGORY_SPECS, get_spec_config

__all__ = [
    "extract_sku",
    "extract_breadcrumbs",
    "extract_description_and_specs",
    "extract_primary_image_url",
    "extract_next_page_url",
    "extract_current_page",
    "extract_total_pages",
    "pick_spec",
    "map_category_specs",
    "is_product_url",
]

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
    # Try multiple selectors for the description container
    desc_container = None
    selectors = [
        'div.description[data-overlay="product-description"] div.site-text',
        'div.description div.site-text',
        'div.description',
        '[data-overlay="product-description"]',
    ]
    
    for selector in selectors:
        desc_container = soup.select_one(selector)
        if desc_container:
            break
    
    if not desc_container:
        return None, {}

    # Full description as plain text (excluding spec labels/values for cleaner text)
    # First, get the prose text before the specs
    description_parts = []
    for element in desc_container.children:
        if hasattr(element, 'name'):
            # Skip dl (specs), h3 (headers like "Specifications:")
            if element.name in ('dl', 'h3', 'h4'):
                continue
            # Get text from paragraphs, divs, etc.
            text = element.get_text(strip=True)
            if text:
                description_parts.append(text)
        elif isinstance(element, str) and element.strip():
            description_parts.append(element.strip())
    
    # If no structured parts found, fall back to full text
    if description_parts:
        description_text = " ".join(description_parts)
    else:
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
    """Extract the first real product image URL from the page.
    
    Prioritizes:
    1. og:image meta tag (most reliable, always present)
    2. Product gallery images
    3. Any product image in the page
    
    Returns the full URL of the product image, or None if not found.
    """
    # Method 1: og:image meta tag (most reliable)
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        return og_image["content"]
    
    # Method 2: Look for product gallery/main image
    # bike-components uses fancybox for gallery
    gallery_img = soup.select_one('a.js-fancybox-productimage[data-src]')
    if gallery_img and gallery_img.get("data-src"):
        return gallery_img["data-src"]
    
    # Method 3: Look for main product image in gallery area
    gallery_selectors = [
        'div.area-gallery img.site-image',
        'div.gallery-main img[src]',
        'div.product-image img[src]',
        'div.product-media img[src]',
    ]
    for selector in gallery_selectors:
        img = soup.select_one(selector)
        if img:
            src = img.get("src") or img.get("data-src")
            if src and "assets/p/" in src:  # Product image path pattern
                return src
    
    # Method 4: Look in JSON-LD structured data
    script = soup.find("script", type="application/ld+json")
    if script:
        try:
            import json
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "Product":
                    images = item.get("image", [])
                    if isinstance(images, list) and images:
                        first_img = images[0]
                        if isinstance(first_img, dict):
                            return first_img.get("url")
                        elif isinstance(first_img, str):
                            return first_img
                    elif isinstance(images, dict):
                        return images.get("url")
        except (json.JSONDecodeError, TypeError, KeyError):
            pass
    
    return None


# =============================================================================
# Pagination Extraction
# =============================================================================

def extract_next_page_url(soup: BeautifulSoup, current_url: str) -> Optional[str]:
    """Extract the next page URL from a category listing page.
    
    Looks for:
    1. <link rel="next" href="...">
    2. Pagination links with ?page=N
    
    Returns the full URL of the next page, or None if no next page.
    """
    # Method 1: <link rel="next">
    next_link = soup.find("link", rel="next")
    if next_link and next_link.get("href"):
        return next_link["href"]
    
    # Method 2: Look for pagination navigation
    # Common patterns: <a href="?page=2">, <a class="next">, etc.
    pagination = soup.select_one('nav.pagination, div.pagination, ul.pagination')
    if pagination:
        # Look for "next" link
        next_btn = pagination.select_one('a[rel="next"], a.next, a:contains("Next")')
        if next_btn and next_btn.get("href"):
            return urljoin(current_url, next_btn["href"])
        
        # Look for numbered pages and find current + 1
        current_page = extract_current_page(current_url)
        next_page_link = pagination.select_one(f'a[href*="page={current_page + 1}"]')
        if next_page_link:
            return urljoin(current_url, next_page_link["href"])
    
    return None


def extract_current_page(url: str) -> int:
    """Extract the current page number from a URL. Returns 1 if not found."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    page_values = params.get("page", ["1"])
    try:
        return int(page_values[0])
    except (ValueError, IndexError):
        return 1


def extract_total_pages(soup: BeautifulSoup) -> Optional[int]:
    """Try to extract the total number of pages from pagination.
    
    Returns None if unable to determine.
    """
    # Look for pagination with page numbers
    pagination = soup.select_one('nav.pagination, div.pagination, ul.pagination')
    if not pagination:
        return None
    
    # Find all page links and get the highest number
    page_links = pagination.select('a[href*="page="]')
    max_page = 1
    for link in page_links:
        href = link.get("href", "")
        match = re.search(r'page=(\d+)', href)
        if match:
            page_num = int(match.group(1))
            max_page = max(max_page, page_num)
    
    # Also check for text like "Page 1 of 5" or "1/5"
    pagination_text = pagination.get_text()
    of_match = re.search(r'of\s+(\d+)', pagination_text, re.IGNORECASE)
    if of_match:
        return int(of_match.group(1))
    
    return max_page if max_page > 1 else None


# =============================================================================
# Generic Spec Mapping (Registry-based)
# =============================================================================

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


def map_category_specs(category: str, specs: Dict[str, str]) -> Dict[str, Optional[str]]:
    """Map raw specs dict into normalized category-specific fields.
    
    Uses the CATEGORY_SPECS registry from config.py to determine field mappings.
    Returns a dict with keys matching the database column names.
    """
    if not specs:
        return {}
    
    spec_config = get_spec_config(category)
    if not spec_config:
        return {}
    
    field_mappings = spec_config.get("field_mappings", {})
    result: Dict[str, Optional[str]] = {}
    
    for db_column, html_labels in field_mappings.items():
        result[db_column] = pick_spec(specs, html_labels)
    
    return result


def is_product_url(href: str) -> bool:
    """Check if a URL looks like a product detail page."""
    return PRODUCT_URL_RE.match(href) is not None
