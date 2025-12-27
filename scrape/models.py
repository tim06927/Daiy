"""Data models for products."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

__all__ = ["Product"]


@dataclass
class Product:
    """Represents a single product scraped from bike-components.de
    
    Core fields are stored in the main products table.
    Category-specific specs are stored in separate tables via category_specs.
    """

    # Required fields
    category: str
    name: str
    url: str

    # Core optional fields (stored in products table)
    image_url: Optional[str] = None
    brand: Optional[str] = None
    price_text: Optional[str] = None
    sku: Optional[str] = None
    breadcrumbs: Optional[str] = None
    description: Optional[str] = None

    # Raw specs dict from HTML (stored as JSON in products table)
    specs: Optional[Dict[str, str]] = None

    # Category-specific normalized specs (stored in category-specific table)
    # Keys match the column names in the respective spec table
    category_specs: Dict[str, Any] = field(default_factory=dict)

    # Database ID (set after insert/update)
    id: Optional[int] = None

