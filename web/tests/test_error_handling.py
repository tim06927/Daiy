"""Test error handling and edge cases."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Setup path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestExtractCategoriesErrorHandling:
    """Test error handling in category extraction."""

    def test_extract_categories_with_malformed_brackets(self):
        """Test category extraction with incomplete bracket syntax."""
        from job_identification import extract_categories_from_instructions

        instructions = [
            "Step 1: Use [drivetrain_tools",  # Missing closing bracket
            "Step 2: Install drivetrain_chains]",  # Missing opening bracket
        ]
        result = extract_categories_from_instructions(instructions)
        # Should not crash, just ignore malformed ones
        assert isinstance(result, list)

    def test_extract_categories_with_empty_brackets(self):
        """Test with empty bracket content."""
        from job_identification import extract_categories_from_instructions

        instructions = ["Step 1: Use []", "Step 2: Install [drivetrain_chains]"]
        result = extract_categories_from_instructions(instructions)
        # Should handle gracefully
        assert "drivetrain_chains" in result

    def test_extract_categories_with_none_input(self):
        """Test with None input."""
        from job_identification import extract_categories_from_instructions

        # Should handle None gracefully
        try:
            result = extract_categories_from_instructions(None)
            # If it doesn't crash, result should be empty or list
            assert isinstance(result, (list, type(None)))
        except (TypeError, AttributeError):
            # It's acceptable to raise TypeError for None input
            pass

    def test_extract_categories_empty_list(self):
        """Test with empty instruction list."""
        from job_identification import extract_categories_from_instructions

        result = extract_categories_from_instructions([])
        assert result == []


class TestUnclearSpecificationEdgeCases:
    """Test UnclearSpecification edge cases."""

    def test_unclear_spec_with_empty_options(self):
        """Test creating spec with empty options."""
        from job_identification import UnclearSpecification

        spec = UnclearSpecification(
            spec_name="test",
            confidence=0.5,
            question="?",
            hint="hint",
            options=[],
        )
        assert spec.options == []

    def test_unclear_spec_with_very_low_confidence(self):
        """Test with confidence close to zero."""
        from job_identification import UnclearSpecification

        spec = UnclearSpecification(
            spec_name="test",
            confidence=0.001,
            question="?",
            hint="hint",
            options=["a"],
        )
        assert spec.confidence == 0.001

    def test_unclear_spec_with_very_high_confidence(self):
        """Test with confidence close to one."""
        from job_identification import UnclearSpecification

        spec = UnclearSpecification(
            spec_name="test",
            confidence=0.999,
            question="?",
            hint="hint",
            options=["a"],
        )
        assert spec.confidence == 0.999

    def test_unclear_spec_with_long_strings(self):
        """Test with very long question/hint strings."""
        from job_identification import UnclearSpecification

        long_string = "x" * 10000
        spec = UnclearSpecification(
            spec_name="test",
            confidence=0.5,
            question=long_string,
            hint=long_string,
            options=["a"],
        )
        assert len(spec.question) == 10000
        assert len(spec.hint) == 10000

    def test_unclear_spec_with_special_characters(self):
        """Test with special characters in strings."""
        from job_identification import UnclearSpecification

        spec = UnclearSpecification(
            spec_name="test",
            confidence=0.5,
            question="What's ñoño? [Special {chars}]",
            hint="Hint with émojis 🚴",
            options=["café", "naïve"],
        )
        assert "ñoño" in spec.question
        assert "🚴" in spec.hint


class TestJobIdentificationEdgeCases:
    """Test JobIdentification edge cases."""

    def test_job_with_many_instructions(self):
        """Test job with many instructions."""
        from job_identification import JobIdentification

        instructions = [f"Step {i}: Do something" for i in range(100)]
        job = JobIdentification(
            instructions=instructions,
            unclear_specifications=[],
            confidence=0.9,
            reasoning="Test",
        )
        assert len(job.instructions) == 100

    def test_job_with_nested_brackets_in_instructions(self):
        """Test category extraction with nested brackets."""
        from job_identification import JobIdentification

        job = JobIdentification(
            instructions=[
                "Step 1: Use [[drivetrain_tools]]",
                "Step 2: Check [inner [drivetrain_chains]]",
            ],
            unclear_specifications=[],
            confidence=0.9,
            reasoning="Test",
        )
        # Should handle nested brackets without crashing
        categories = job.referenced_categories
        assert isinstance(categories, list)

    def test_job_with_similar_category_names(self):
        """Test extraction with similar category names."""
        from job_identification import JobIdentification

        job = JobIdentification(
            instructions=[
                "Use [drivetrain]",
                "Then [drivetrain_chains]",
                "Then [drivetrain_cassettes]",
            ],
            unclear_specifications=[],
            confidence=0.9,
            reasoning="Test",
        )
        categories = job.referenced_categories
        # All three should be extracted
        assert len(categories) == 3


class TestAPIErrorHandling:
    """Test API error handling."""

    @pytest.fixture
    def client(self, mock_csv_path, monkeypatch):
        """Create Flask test client with consent already granted."""
        monkeypatch.setenv("CSV_PATH", mock_csv_path)
        from app import app

        app.config['TESTING'] = True
        with app.test_client() as test_client:
            # Set consent in session to bypass consent gate
            with test_client.session_transaction() as sess:
                sess['alpha_consent'] = True
                sess['alpha_consent_ts'] = '2025-01-01T00:00:00+00:00'
            yield test_client

    def test_recommend_with_very_long_text(self, client):
        """Test with extremely long problem_text."""
        long_text = "x" * 50000
        response = client.post(
            '/api/recommend',
            json={"problem_text": long_text},
            content_type='application/json'
        )
        # Should not crash (500 error)
        assert response.status_code != 500

    def test_recommend_with_unicode_text(self, client):
        """Test with unicode characters."""
        response = client.post(
            '/api/recommend',
            json={"problem_text": "Need 自転車 parts for moje kolo 🚴"},
            content_type='application/json'
        )
        assert response.status_code != 500

    def test_recommend_with_null_problem_text(self, client):
        """Test with null problem_text."""
        response = client.post(
            '/api/recommend',
            json={"problem_text": None},
            content_type='application/json'
        )
        assert response.status_code in [400, 500]

    def test_recommend_with_number_problem_text(self, client):
        """Test with number instead of string."""
        response = client.post(
            '/api/recommend',
            json={"problem_text": 12345},
            content_type='application/json'
        )
        # Should handle type mismatch gracefully
        assert response.status_code in [400, 200]

    def test_recommend_with_dict_problem_text(self, client):
        """Test with dict instead of string."""
        response = client.post(
            '/api/recommend',
            json={"problem_text": {"nested": "object"}},
            content_type='application/json'
        )
        assert response.status_code == 400


class TestDataValidation:
    """Test data validation and type checking."""

    def test_unclear_spec_confidence_boundary(self):
        """Test confidence boundary values."""
        from job_identification import UnclearSpecification

        # Test exact boundaries
        for conf in [0.0, 0.5, 1.0]:
            spec = UnclearSpecification(
                spec_name="test",
                confidence=conf,
                question="?",
                hint="h",
                options=["a"],
            )
            assert spec.confidence == conf

    def test_job_referenced_categories_type(self):
        """Test that referenced_categories always returns list."""
        from job_identification import JobIdentification

        job = JobIdentification(
            instructions=[],
            unclear_specifications=[],
            confidence=0.5,
            reasoning="Test",
        )
        cats = job.referenced_categories
        assert isinstance(cats, list)

    def test_job_to_dict_contains_all_fields(self):
        """Test that to_dict includes all necessary fields."""
        from job_identification import JobIdentification, UnclearSpecification

        spec = UnclearSpecification(
            spec_name="test",
            confidence=0.5,
            question="?",
            hint="h",
            options=["a"],
        )
        job = JobIdentification(
            instructions=["Step"],
            unclear_specifications=[spec],
            confidence=0.8,
            reasoning="Test",
        )
        job_dict = job.to_dict()

        required_fields = [
            "instructions",
            "unclear_specifications",
            "confidence",
            "reasoning",
        ]
        for field in required_fields:
            assert field in job_dict, f"Missing field: {field}"
