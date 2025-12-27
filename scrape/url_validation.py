"""URL validation and sanitization utilities.

Provides security-focused URL validation for scraped content.
"""

import re
from typing import Optional, Set
from urllib.parse import urlparse

__all__ = [
    "validate_url",
    "validate_product_url",
    "validate_image_url",
    "sanitize_url",
    "URLValidationError",
    "ALLOWED_DOMAINS",
]


class URLValidationError(Exception):
    """Raised when URL validation fails."""
    pass


# Domains we trust for scraping
ALLOWED_DOMAINS: Set[str] = frozenset({
    "www.bike-components.de",
    "bike-components.de",
    # CDN domains for images
    "assets.bike-components.de",
    "media.bike-components.de",
})

# Pattern for product URLs: /en/Brand/Product-Name-p12345/
PRODUCT_URL_PATTERN = re.compile(
    r"^https://www\.bike-components\.de/en/[^/]+/.+-p\d+/?$"
)

# Pattern for image URLs
IMAGE_URL_PATTERN = re.compile(
    r"^https?://[a-zA-Z0-9.-]+\.(de|com|net)/.*\.(jpg|jpeg|png|webp|avif|gif)(\?.*)?$",
    re.IGNORECASE
)

# Dangerous URL schemes to reject
DANGEROUS_SCHEMES = {"javascript", "data", "vbscript", "file"}


def sanitize_url(url: str) -> str:
    """Sanitize a URL by stripping whitespace and normalizing.

    Args:
        url: Raw URL string

    Returns:
        Sanitized URL string
    """
    if not url:
        return ""
    
    # Strip whitespace and control characters
    url = url.strip()
    url = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", url)
    
    # Remove any null bytes or other injection attempts
    url = url.replace("\x00", "").replace("%00", "")
    
    return url


def validate_url(
    url: str,
    allowed_domains: Optional[Set[str]] = None,
    require_https: bool = False,
) -> str:
    """Validate a URL for safety.

    Args:
        url: URL to validate
        allowed_domains: Set of allowed domains (default: ALLOWED_DOMAINS)
        require_https: Whether to require HTTPS scheme

    Returns:
        Validated URL

    Raises:
        URLValidationError: If URL is invalid or from untrusted domain
    """
    if not url:
        raise URLValidationError("URL is empty")
    
    # Sanitize first
    url = sanitize_url(url)
    
    # Parse the URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise URLValidationError(f"Failed to parse URL: {e}") from e
    
    # Check scheme
    scheme = parsed.scheme.lower()
    if scheme in DANGEROUS_SCHEMES:
        raise URLValidationError(f"Dangerous URL scheme: {scheme}")
    
    if require_https and scheme != "https":
        raise URLValidationError(f"URL must use HTTPS, got: {scheme}")
    
    if scheme not in ("http", "https"):
        raise URLValidationError(f"Invalid URL scheme: {scheme}")
    
    # Check domain
    domain = parsed.netloc.lower()
    if not domain:
        raise URLValidationError("URL has no domain")
    
    # Strip port if present for domain check
    domain_without_port = domain.split(":")[0]
    
    domains_to_check = allowed_domains if allowed_domains is not None else ALLOWED_DOMAINS
    if domains_to_check and domain_without_port not in domains_to_check:
        raise URLValidationError(
            f"URL domain '{domain_without_port}' not in allowed domains: {domains_to_check}"
        )
    
    # Check for suspicious patterns
    suspicious_patterns = [
        r"\.\.\/",           # Path traversal
        r"%2e%2e",           # Encoded path traversal
        r"<script",          # XSS attempt
        r"javascript:",      # JS injection
    ]
    
    url_lower = url.lower()
    for pattern in suspicious_patterns:
        if re.search(pattern, url_lower):
            raise URLValidationError(f"URL contains suspicious pattern: {pattern}")
    
    return url


def validate_product_url(url: str) -> str:
    """Validate a product page URL.

    Args:
        url: Product URL to validate

    Returns:
        Validated URL

    Raises:
        URLValidationError: If URL is not a valid product URL
    """
    url = validate_url(url, require_https=True)
    
    if not PRODUCT_URL_PATTERN.match(url):
        raise URLValidationError(
            f"URL does not match product pattern: {url}\n"
            f"Expected: https://www.bike-components.de/en/Brand/Product-p12345/"
        )
    
    return url


def validate_image_url(url: str) -> str:
    """Validate an image URL.

    Args:
        url: Image URL to validate

    Returns:
        Validated URL

    Raises:
        URLValidationError: If URL is not a valid image URL
    """
    # Allow None/empty for optional images
    if not url:
        return ""
    
    # For images, we allow a broader set of domains (CDNs, etc.)
    # but still check the format
    url = sanitize_url(url)
    
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise URLValidationError(f"Failed to parse image URL: {e}") from e
    
    scheme = parsed.scheme.lower()
    if scheme in DANGEROUS_SCHEMES:
        raise URLValidationError(f"Dangerous URL scheme in image: {scheme}")
    
    if scheme not in ("http", "https"):
        raise URLValidationError(f"Invalid image URL scheme: {scheme}")
    
    # Basic format check - should look like an image URL
    if not IMAGE_URL_PATTERN.match(url):
        # Allow CDN URLs that might not have extensions
        if "assets" not in url.lower() and "media" not in url.lower():
            raise URLValidationError(f"URL does not look like an image: {url}")
    
    return url


def is_safe_url(url: str) -> bool:
    """Check if a URL is safe without raising exceptions.

    Args:
        url: URL to check

    Returns:
        True if URL is safe, False otherwise
    """
    try:
        validate_url(url)
        return True
    except URLValidationError:
        return False
