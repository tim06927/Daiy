"""Tests for the dynamic specs system.

Tests the new flexible spec storage that automatically normalizes specs
for any category based on discovered field mappings.
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

from scrape.db import (
    get_connection,
    get_discovered_fields,
    get_dynamic_specs,
    init_db,
    save_discovered_fields,
    upsert_dynamic_specs,
    upsert_product,
)
from scrape.html_utils import map_dynamic_specs


class TestDynamicSpecsTable:
    """Tests for dynamic_specs table operations."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        init_db(db_path)
        yield db_path
        # Cleanup
        Path(db_path).unlink(missing_ok=True)

    def test_init_db_creates_dynamic_specs_table(self, temp_db):
        """Verify init_db creates the dynamic_specs table."""
        with get_connection(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='dynamic_specs'"
            )
            assert cursor.fetchone() is not None

    def test_init_db_creates_discovered_fields_table(self, temp_db):
        """Verify init_db creates the discovered_fields table."""
        with get_connection(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='discovered_fields'"
            )
            assert cursor.fetchone() is not None

    def test_upsert_and_get_dynamic_specs(self, temp_db):
        """Test inserting and retrieving dynamic specs."""
        # Create a product first
        product_id = upsert_product(
            db_path=temp_db,
            category="saddles",
            name="Test Saddle",
            url="https://example.com/saddle-p123/",
        )

        # Insert dynamic specs
        specs = {
            "width": "143mm",
            "length": "280mm",
            "material": "Carbon",
            "weight": "180g",
        }
        upsert_dynamic_specs(temp_db, product_id, "saddles", specs)

        # Retrieve and verify
        retrieved = get_dynamic_specs(temp_db, product_id)
        assert retrieved == specs

    def test_upsert_dynamic_specs_updates_existing(self, temp_db):
        """Test that upsert updates existing specs."""
        product_id = upsert_product(
            db_path=temp_db,
            category="saddles",
            name="Test Saddle",
            url="https://example.com/saddle-p124/",
        )

        # Initial insert
        upsert_dynamic_specs(temp_db, product_id, "saddles", {"width": "143mm"})

        # Update with new value
        upsert_dynamic_specs(temp_db, product_id, "saddles", {"width": "155mm", "length": "280mm"})

        retrieved = get_dynamic_specs(temp_db, product_id)
        assert retrieved["width"] == "155mm"
        assert retrieved["length"] == "280mm"


class TestDiscoveredFields:
    """Tests for discovered_fields table operations."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        init_db(db_path)
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    def test_save_and_get_discovered_fields(self, temp_db):
        """Test saving and retrieving discovered fields."""
        fields = [
            {
                "field_name": "width",
                "original_labels": ["Width", "Breite"],
                "frequency": 0.95,
                "sample_values": ["143mm", "155mm"],
            },
            {
                "field_name": "length",
                "original_labels": ["Length", "Länge"],
                "frequency": 0.90,
                "sample_values": ["280mm", "275mm"],
            },
        ]

        save_discovered_fields(temp_db, "saddles", fields)

        retrieved = get_discovered_fields(temp_db, "saddles")
        assert len(retrieved) == 2
        assert retrieved[0]["field_name"] == "width"
        assert retrieved[0]["frequency"] == 0.95
        assert "Width" in retrieved[0]["original_labels"]

    def test_save_discovered_fields_replaces_existing(self, temp_db):
        """Test that saving replaces existing fields for the category."""
        # Initial save
        save_discovered_fields(
            temp_db,
            "saddles",
            [{"field_name": "width", "original_labels": ["Width"], "frequency": 0.9}],
        )

        # Save again with different fields
        save_discovered_fields(
            temp_db,
            "saddles",
            [{"field_name": "material", "original_labels": ["Material"], "frequency": 0.8}],
        )

        retrieved = get_discovered_fields(temp_db, "saddles")
        assert len(retrieved) == 1
        assert retrieved[0]["field_name"] == "material"


class TestMapDynamicSpecs:
    """Tests for the map_dynamic_specs function."""

    def test_map_dynamic_specs_basic(self):
        """Test basic spec mapping with discovered fields."""
        raw_specs = {
            "Width": "143mm",
            "Length": "280mm",
            "Material": "Carbon",
        }

        discovered_fields = [
            {"field_name": "width", "original_labels": ["Width", "Breite"]},
            {"field_name": "length", "original_labels": ["Length", "Länge"]},
            {"field_name": "material", "original_labels": ["Material"]},
        ]

        result = map_dynamic_specs(raw_specs, discovered_fields)

        assert result["width"] == "143mm"
        assert result["length"] == "280mm"
        assert result["material"] == "Carbon"

    def test_map_dynamic_specs_case_insensitive(self):
        """Test that mapping is case-insensitive."""
        raw_specs = {"WIDTH": "143mm", "material": "Carbon"}

        discovered_fields = [
            {"field_name": "width", "original_labels": ["Width"]},
            {"field_name": "material", "original_labels": ["Material"]},
        ]

        result = map_dynamic_specs(raw_specs, discovered_fields)

        assert result["width"] == "143mm"
        assert result["material"] == "Carbon"

    def test_map_dynamic_specs_missing_fields(self):
        """Test that missing fields are not included."""
        raw_specs = {"Width": "143mm"}

        discovered_fields = [
            {"field_name": "width", "original_labels": ["Width"]},
            {"field_name": "length", "original_labels": ["Length"]},
        ]

        result = map_dynamic_specs(raw_specs, discovered_fields)

        assert result["width"] == "143mm"
        assert "length" not in result

    def test_map_dynamic_specs_empty_input(self):
        """Test with empty inputs."""
        assert map_dynamic_specs({}, []) == {}
        assert map_dynamic_specs({"Width": "143mm"}, []) == {}
        assert map_dynamic_specs({}, [{"field_name": "width", "original_labels": ["Width"]}]) == {}


class TestIntegration:
    """Integration tests for the full dynamic specs workflow."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        init_db(db_path)
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    def test_full_workflow(self, temp_db):
        """Test the complete flow: discover fields -> scrape -> store -> export."""
        # Step 1: Save discovered fields (simulating field discovery)
        discovered_fields = [
            {"field_name": "width", "original_labels": ["Width", "Saddle Width"], "frequency": 0.95},
            {"field_name": "material", "original_labels": ["Material", "Shell Material"], "frequency": 0.85},
            {"field_name": "weight", "original_labels": ["Weight"], "frequency": 0.80},
        ]
        save_discovered_fields(temp_db, "saddles", discovered_fields)

        # Step 2: Create a product
        product_id = upsert_product(
            db_path=temp_db,
            category="saddles",
            name="Pro Saddle",
            url="https://example.com/pro-saddle-p999/",
        )

        # Step 3: Simulate scraping and mapping specs
        raw_specs = {
            "Width": "143mm",
            "Shell Material": "Carbon fiber reinforced nylon",
            "Weight": "195g",
            "Color": "Black",  # Not in discovered fields
        }

        # Load discovered fields from DB
        loaded_fields = get_discovered_fields(temp_db, "saddles")

        # Map raw specs to normalized fields
        normalized_specs = map_dynamic_specs(raw_specs, loaded_fields)

        # Step 4: Store dynamic specs
        upsert_dynamic_specs(temp_db, product_id, "saddles", normalized_specs)

        # Step 5: Verify stored specs
        stored_specs = get_dynamic_specs(temp_db, product_id)

        assert stored_specs["width"] == "143mm"
        assert stored_specs["material"] == "Carbon fiber reinforced nylon"
        assert stored_specs["weight"] == "195g"
        assert "color" not in stored_specs  # Not in discovered fields
