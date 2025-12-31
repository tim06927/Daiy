"""Test JobIdentification and UnclearSpecification classes."""

import sys
from pathlib import Path

import pytest

# Add web directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job_identification import JobIdentification, UnclearSpecification


class TestUnclearSpecification:
    """Tests for UnclearSpecification class."""

    def test_creation_basic(self):
        """Test creating an unclear specification."""
        spec = UnclearSpecification(
            spec_name="gearing",
            confidence=0.3,
            question="How many speeds?",
            hint="Count cogs",
            options=["8", "10", "12"],
        )
        assert spec.spec_name == "gearing"
        assert spec.confidence == 0.3
        assert len(spec.options) == 3
        assert spec.question == "How many speeds?"
        assert spec.hint == "Count cogs"

    def test_creation_with_zero_confidence(self):
        """Test creating spec with zero confidence."""
        spec = UnclearSpecification(
            spec_name="test",
            confidence=0.0,
            question="Q?",
            hint="H",
            options=["a"],
        )
        assert spec.confidence == 0.0

    def test_creation_with_full_confidence(self):
        """Test creating spec with 100% confidence."""
        spec = UnclearSpecification(
            spec_name="test",
            confidence=1.0,
            question="Q?",
            hint="H",
            options=["a"],
        )
        assert spec.confidence == 1.0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        spec = UnclearSpecification(
            spec_name="use_case",
            confidence=0.5,
            question="Riding style?",
            hint="Road/MTB/Commute",
            options=["road", "mtb", "commute"],
        )
        spec_dict = spec.to_dict()
        
        assert spec_dict["spec_name"] == "use_case"
        assert spec_dict["confidence"] == 0.5
        assert spec_dict["question"] == "Riding style?"
        assert spec_dict["hint"] == "Road/MTB/Commute"
        assert spec_dict["options"] == ["road", "mtb", "commute"]
        assert isinstance(spec_dict, dict)

    @pytest.mark.parametrize(
        "confidence",
        [0.0, 0.25, 0.5, 0.75, 1.0],
    )
    def test_confidence_values(self, confidence):
        """Test various confidence levels."""
        spec = UnclearSpecification(
            spec_name="test",
            confidence=confidence,
            question="Test?",
            hint="Hint",
            options=["a", "b"],
        )
        assert 0 <= spec.confidence <= 1

    def test_options_empty_list(self):
        """Test with empty options list."""
        spec = UnclearSpecification(
            spec_name="test",
            confidence=0.5,
            question="Q?",
            hint="H",
            options=[],
        )
        assert spec.options == []

    def test_options_single_item(self):
        """Test with single option."""
        spec = UnclearSpecification(
            spec_name="test",
            confidence=0.5,
            question="Q?",
            hint="H",
            options=["only_one"],
        )
        assert len(spec.options) == 1
        assert spec.options[0] == "only_one"


class TestJobIdentification:
    """Tests for JobIdentification class."""

    def test_creation_basic(self):
        """Test creating a basic job."""
        job = JobIdentification(
            instructions=["Step 1: Remove chain"],
            unclear_specifications=[],
            confidence=0.85,
            reasoning="User needs chain replacement",
        )
        assert len(job.instructions) == 1
        assert job.instructions[0] == "Step 1: Remove chain"
        assert len(job.unclear_specifications) == 0
        assert job.confidence == 0.85
        assert job.reasoning == "User needs chain replacement"

    def test_creation_with_unclear_specs(self):
        """Test creating job with unclear specifications."""
        spec = UnclearSpecification(
            spec_name="gearing",
            confidence=0.3,
            question="Speed?",
            hint="Count",
            options=["10", "12"],
        )
        job = JobIdentification(
            instructions=["Step 1: Remove chain"],
            unclear_specifications=[spec],
            confidence=0.85,
            reasoning="User needs chain",
        )
        assert len(job.instructions) == 1
        assert len(job.unclear_specifications) == 1
        assert job.unclear_specifications[0].spec_name == "gearing"

    def test_creation_with_multiple_instructions(self):
        """Test creating job with multiple instructions."""
        instructions = [
            "Step 1: Remove wheel",
            "Step 2: Check drivetrain",
            "Step 3: Install new cassette",
        ]
        job = JobIdentification(
            instructions=instructions,
            unclear_specifications=[],
            confidence=0.9,
            reasoning="Complex upgrade",
        )
        assert len(job.instructions) == 3
        assert job.instructions == instructions

    def test_referenced_categories_extraction(self):
        """Test that category references are extracted from instructions."""
        job = JobIdentification(
            instructions=[
                "Step 1: Remove [drivetrain_tools]",
                "Step 2: Install [drivetrain_chains]",
            ],
            unclear_specifications=[],
            confidence=0.9,
            reasoning="Test",
        )
        categories = job.referenced_categories
        assert "drivetrain_tools" in categories
        assert "drivetrain_chains" in categories
        assert len(categories) == 2

    def test_referenced_categories_unique(self):
        """Test that category extraction avoids duplicates."""
        job = JobIdentification(
            instructions=[
                "Step 1: Use [drivetrain_tools]",
                "Step 2: Use [drivetrain_tools]",
                "Step 3: Install [drivetrain_chains]",
            ],
            unclear_specifications=[],
            confidence=0.9,
            reasoning="Test",
        )
        categories = job.referenced_categories
        # Should be unique
        assert categories.count("drivetrain_tools") == 1
        assert len(categories) == 2

    def test_referenced_categories_no_matches(self):
        """Test extraction when no categories referenced."""
        job = JobIdentification(
            instructions=["Step 1: Clean the bike"],
            unclear_specifications=[],
            confidence=0.9,
            reasoning="Test",
        )
        categories = job.referenced_categories
        assert len(categories) == 0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        spec = UnclearSpecification(
            spec_name="gearing",
            confidence=0.4,
            question="Speed?",
            hint="Count",
            options=["10", "12"],
        )
        job = JobIdentification(
            instructions=["Step 1"],
            unclear_specifications=[spec],
            confidence=0.85,
            reasoning="Test job",
        )
        job_dict = job.to_dict()

        # Verify all fields present
        assert "instructions" in job_dict
        assert "unclear_specifications" in job_dict
        assert "confidence" in job_dict
        assert "reasoning" in job_dict
        assert job_dict["confidence"] == 0.85
        assert len(job_dict["instructions"]) == 1
        assert len(job_dict["unclear_specifications"]) == 1

    def test_empty_instructions(self):
        """Test job with no instructions."""
        job = JobIdentification(
            instructions=[],
            unclear_specifications=[],
            confidence=0.5,
            reasoning="Ambiguous request",
        )
        assert len(job.instructions) == 0

    def test_multiple_unclear_specs(self):
        """Test job with multiple unclear specifications."""
        specs = [
            UnclearSpecification(
                spec_name="gearing",
                confidence=0.3,
                question="Speed?",
                hint="Count",
                options=["10", "12"],
            ),
            UnclearSpecification(
                spec_name="use_case",
                confidence=0.4,
                question="Type?",
                hint="Road/MTB",
                options=["road", "mtb"],
            ),
        ]
        job = JobIdentification(
            instructions=["Step 1"],
            unclear_specifications=specs,
            confidence=0.6,
            reasoning="Ambiguous request",
        )
        assert len(job.unclear_specifications) == 2
        assert job.unclear_specifications[0].spec_name == "gearing"
        assert job.unclear_specifications[1].spec_name == "use_case"

    def test_confidence_boundary_values(self):
        """Test job confidence at boundaries."""
        for conf in [0.0, 0.5, 1.0]:
            job = JobIdentification(
                instructions=["Step 1"],
                unclear_specifications=[],
                confidence=conf,
                reasoning="Test",
            )
            assert job.confidence == conf
