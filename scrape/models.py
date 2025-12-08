"""Data models for products."""

from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class Product:
    """Represents a single product scraped from bike-components.de"""
    
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
