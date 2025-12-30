"""Tests for candidate selection helpers."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from candidate_selection import prepare_product_for_response  # noqa: E402


def test_prepare_product_for_response_normalizes_image_url():
    row = pd.Series(
        {
            "name": "Test product",
            "url": "https://example.com/product",
            "brand": "Brand",
            "price_text": "10€",
            "application": "Road",
            "speed": 11,
            "specs_dict": {"a": "b"},
            "image_url": "/assets/example.jpg",
        }
    )

    result = prepare_product_for_response(row)

    assert result["image_url"] == "https://www.bike-components.de/assets/example.jpg"


def test_prepare_product_for_response_handles_missing_image_url():
    row = pd.Series(
        {
            "name": "Test product",
            "url": "https://example.com/product",
            "brand": "Brand",
            "price_text": "10€",
            "application": "Road",
            "speed": 11,
            "specs_dict": {"a": "b"},
            "image_url": None,
        }
    )

    result = prepare_product_for_response(row)

    assert result["image_url"] is None
