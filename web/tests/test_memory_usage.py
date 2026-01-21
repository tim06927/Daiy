"""Tests for memory usage during user flow.

Ensures the application stays within memory limits suitable for
Render's 512MB free tier deployment.
"""

import gc
import sys
from pathlib import Path

import pytest

# Setup path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def get_memory_mb():
    """Get current process memory usage in MB."""
    try:
        import psutil
        import os
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        pytest.skip("psutil not installed - skipping memory test")


class TestMemoryUsage:
    """Test memory stays within acceptable limits."""

    # Maximum allowed memory in MB (leave headroom for 512MB limit)
    MAX_MEMORY_MB = 200
    
    # Maximum spike allowed during a single operation
    MAX_SPIKE_MB = 50

    def test_category_validation_memory_efficient(self):
        """Test that category validation doesn't load full catalog."""
        gc.collect()
        baseline = get_memory_mb()
        
        from candidate_selection import validate_categories
        
        # Validate some categories
        valid = validate_categories([
            'drivetrain_cassettes',
            'drivetrain_chains',
            'drivetrain_derailleurs_rear',
        ])
        
        gc.collect()
        after = get_memory_mb()
        spike = after - baseline
        
        assert spike < self.MAX_SPIKE_MB, (
            f"Category validation caused {spike:.1f}MB spike "
            f"(max allowed: {self.MAX_SPIKE_MB}MB). "
            "This suggests full catalog is being loaded."
        )
        assert len(valid) > 0, "Should find valid categories"

    def test_get_categories_memory_efficient(self):
        """Test that getting categories uses SQL query, not full load."""
        gc.collect()
        baseline = get_memory_mb()
        
        from catalog import get_categories
        
        categories = get_categories()
        
        gc.collect()
        after = get_memory_mb()
        spike = after - baseline
        
        assert spike < self.MAX_SPIKE_MB, (
            f"get_categories() caused {spike:.1f}MB spike "
            f"(max allowed: {self.MAX_SPIKE_MB}MB). "
            "Should use lightweight SQL query."
        )
        assert len(categories) > 100, "Should have many categories"

    def test_candidate_selection_memory_efficient(self):
        """Test that selecting candidates queries specific products only."""
        gc.collect()
        baseline = get_memory_mb()
        
        from candidate_selection import select_candidates_dynamic
        
        # Select candidates for a couple categories
        candidates = select_candidates_dynamic(
            ['drivetrain_cassettes', 'drivetrain_chains'],
            {}  # No filters
        )
        
        gc.collect()
        after = get_memory_mb()
        spike = after - baseline
        
        assert spike < self.MAX_SPIKE_MB, (
            f"Candidate selection caused {spike:.1f}MB spike "
            f"(max allowed: {self.MAX_SPIKE_MB}MB). "
            "Should query limited products per category."
        )
        # Should have candidates for both categories
        assert len(candidates) >= 1, "Should have candidate categories"

    def test_full_request_flow_memory(self):
        """Test memory usage through a simulated request flow.
        
        This simulates the key steps in /api/recommend without
        actually calling the LLM.
        """
        gc.collect()
        baseline = get_memory_mb()
        
        # Step 1: Import modules (simulates app startup)
        from categories import PRODUCT_CATEGORIES
        from catalog import get_categories
        from candidate_selection import (
            validate_categories,
            select_candidates_dynamic,
        )
        
        gc.collect()
        after_imports = get_memory_mb()
        
        # Step 2: Validate categories (happens on every request)
        test_categories = ['drivetrain_cassettes', 'drivetrain_chains']
        valid_categories = validate_categories(test_categories)
        
        gc.collect()
        after_validation = get_memory_mb()
        
        # Step 3: Select candidates (happens on every request)
        candidates = select_candidates_dynamic(valid_categories, {})
        
        gc.collect()
        after_candidates = get_memory_mb()
        
        # Report memory at each stage
        print(f"\nMemory usage:")
        print(f"  Baseline:         {baseline:.1f} MB")
        print(f"  After imports:    {after_imports:.1f} MB (+{after_imports - baseline:.1f})")
        print(f"  After validation: {after_validation:.1f} MB (+{after_validation - after_imports:.1f})")
        print(f"  After candidates: {after_candidates:.1f} MB (+{after_candidates - after_validation:.1f})")
        print(f"  Total spike:      {after_candidates - baseline:.1f} MB")
        
        # Assert total memory stays under limit
        assert after_candidates < self.MAX_MEMORY_MB, (
            f"Total memory {after_candidates:.1f}MB exceeds limit of {self.MAX_MEMORY_MB}MB"
        )
        
        # Assert no single step causes excessive spike
        import_spike = after_imports - baseline
        validation_spike = after_validation - after_imports
        candidate_spike = after_candidates - after_validation
        
        # Imports can be larger due to pandas, etc.
        assert import_spike < 100, f"Import spike too large: {import_spike:.1f}MB"
        assert validation_spike < self.MAX_SPIKE_MB, f"Validation spike too large: {validation_spike:.1f}MB"
        assert candidate_spike < self.MAX_SPIKE_MB, f"Candidate spike too large: {candidate_spike:.1f}MB"

    def test_repeated_requests_no_memory_leak(self):
        """Test that repeated operations don't accumulate memory."""
        from candidate_selection import (
            validate_categories,
            select_candidates_dynamic,
        )
        
        gc.collect()
        baseline = get_memory_mb()
        
        # Simulate 10 requests
        for i in range(10):
            valid = validate_categories(['drivetrain_cassettes'])
            candidates = select_candidates_dynamic(valid, {})
            
            # Force garbage collection between requests
            gc.collect()
        
        after = get_memory_mb()
        growth = after - baseline
        
        # Memory growth should be minimal after repeated requests
        # Allow some growth for caching, but not linear growth
        assert growth < self.MAX_SPIKE_MB, (
            f"Memory grew by {growth:.1f}MB after 10 requests. "
            "Possible memory leak."
        )


class TestNoFullCatalogLoad:
    """Ensure get_catalog() is not called in the request path."""
    
    def test_api_imports_do_not_include_get_catalog(self):
        """Verify api.py doesn't import get_catalog (which loads all data)."""
        api_path = Path(__file__).resolve().parents[1] / "api.py"
        content = api_path.read_text()
        
        # Should not import get_catalog
        assert "from catalog import get_catalog" not in content, (
            "api.py should not import get_catalog - use get_categories instead"
        )
        assert "from .catalog import get_catalog" not in content, (
            "api.py should not import get_catalog - use get_categories instead"
        )
        
        # Should not call _get_catalog_df
        assert "_get_catalog_df()" not in content, (
            "api.py should not use _get_catalog_df() - removed for memory efficiency"
        )

    def test_candidate_selection_uses_query_products(self):
        """Verify candidate_selection uses query_products, not get_catalog."""
        cs_path = Path(__file__).resolve().parents[1] / "candidate_selection.py"
        content = cs_path.read_text()
        
        # Should import query_products
        assert "query_products" in content, (
            "candidate_selection.py should use query_products for efficient queries"
        )
        
        # Should not import get_catalog directly for data loading
        # (it's ok to have validate_categories_against_catalog for backward compat)
        assert "get_catalog()" not in content or "DEPRECATED" in content, (
            "candidate_selection.py should not call get_catalog() directly"
        )
