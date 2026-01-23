"""Test model settings functionality."""

import sys
from pathlib import Path

import pytest

# Setup path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestConfigModelSettings:
    """Test config.py model settings."""

    def test_model_effort_levels_structure(self):
        """Test that MODEL_EFFORT_LEVELS has correct structure."""
        from config import MODEL_EFFORT_LEVELS

        assert isinstance(MODEL_EFFORT_LEVELS, dict)
        assert len(MODEL_EFFORT_LEVELS) > 0

        for model, efforts in MODEL_EFFORT_LEVELS.items():
            assert isinstance(model, str)
            assert isinstance(efforts, list)
            assert len(efforts) > 0
            for effort in efforts:
                assert isinstance(effort, str)

    def test_expected_models_present(self):
        """Test that all expected models are present."""
        from config import MODEL_EFFORT_LEVELS, AVAILABLE_MODELS

        expected_models = ["gpt-5.2", "gpt-5.2-pro", "gpt-5-mini", "gpt-5-nano"]
        for model in expected_models:
            assert model in MODEL_EFFORT_LEVELS
            assert model in AVAILABLE_MODELS

    def test_gpt52_effort_levels(self):
        """Test gpt-5.2 has correct effort levels."""
        from config import MODEL_EFFORT_LEVELS

        expected = ["none", "low", "medium", "high", "xhigh"]
        assert MODEL_EFFORT_LEVELS["gpt-5.2"] == expected

    def test_gpt52_pro_effort_levels(self):
        """Test gpt-5.2-pro has correct effort levels."""
        from config import MODEL_EFFORT_LEVELS

        expected = ["medium", "high", "xhigh"]
        assert MODEL_EFFORT_LEVELS["gpt-5.2-pro"] == expected

    def test_gpt5_mini_effort_levels(self):
        """Test gpt-5-mini has correct effort levels."""
        from config import MODEL_EFFORT_LEVELS

        expected = ["minimal", "low", "medium", "high"]
        assert MODEL_EFFORT_LEVELS["gpt-5-mini"] == expected

    def test_gpt5_nano_effort_levels(self):
        """Test gpt-5-nano has correct effort levels."""
        from config import MODEL_EFFORT_LEVELS

        expected = ["minimal", "low", "medium", "high"]
        assert MODEL_EFFORT_LEVELS["gpt-5-nano"] == expected

    def test_default_model(self):
        """Test that default model is gpt-5-mini."""
        from config import DEFAULT_MODEL

        assert DEFAULT_MODEL == "gpt-5-mini"

    def test_default_effort(self):
        """Test that default effort is low."""
        from config import DEFAULT_EFFORT

        assert DEFAULT_EFFORT == "low"

    def test_default_model_effort_is_valid(self):
        """Test that default model/effort combination is valid."""
        from config import DEFAULT_MODEL, DEFAULT_EFFORT, is_valid_model_effort

        assert is_valid_model_effort(DEFAULT_MODEL, DEFAULT_EFFORT)


class TestIsValidModelEffort:
    """Test is_valid_model_effort function."""

    def test_valid_combinations(self):
        """Test valid model/effort combinations."""
        from config import is_valid_model_effort

        # gpt-5.2 combinations
        assert is_valid_model_effort("gpt-5.2", "none")
        assert is_valid_model_effort("gpt-5.2", "low")
        assert is_valid_model_effort("gpt-5.2", "medium")
        assert is_valid_model_effort("gpt-5.2", "high")
        assert is_valid_model_effort("gpt-5.2", "xhigh")

        # gpt-5.2-pro combinations
        assert is_valid_model_effort("gpt-5.2-pro", "medium")
        assert is_valid_model_effort("gpt-5.2-pro", "high")
        assert is_valid_model_effort("gpt-5.2-pro", "xhigh")

        # gpt-5-mini combinations
        assert is_valid_model_effort("gpt-5-mini", "minimal")
        assert is_valid_model_effort("gpt-5-mini", "low")
        assert is_valid_model_effort("gpt-5-mini", "medium")
        assert is_valid_model_effort("gpt-5-mini", "high")

        # gpt-5-nano combinations
        assert is_valid_model_effort("gpt-5-nano", "minimal")
        assert is_valid_model_effort("gpt-5-nano", "low")

    def test_invalid_effort_for_model(self):
        """Test invalid effort levels for specific models."""
        from config import is_valid_model_effort

        # gpt-5.2-pro doesn't support 'low' or 'none'
        assert not is_valid_model_effort("gpt-5.2-pro", "low")
        assert not is_valid_model_effort("gpt-5.2-pro", "none")
        assert not is_valid_model_effort("gpt-5.2-pro", "minimal")

        # gpt-5-mini doesn't support 'xhigh' or 'none'
        assert not is_valid_model_effort("gpt-5-mini", "xhigh")
        assert not is_valid_model_effort("gpt-5-mini", "none")

    def test_invalid_model(self):
        """Test invalid model names."""
        from config import is_valid_model_effort

        assert not is_valid_model_effort("invalid-model", "low")
        assert not is_valid_model_effort("", "low")
        assert not is_valid_model_effort("gpt-4", "medium")

    def test_invalid_effort(self):
        """Test invalid effort levels."""
        from config import is_valid_model_effort

        assert not is_valid_model_effort("gpt-5-mini", "invalid")
        assert not is_valid_model_effort("gpt-5-mini", "")
        assert not is_valid_model_effort("gpt-5-mini", "super-high")


class TestGetEffortLevelsForModel:
    """Test get_effort_levels_for_model function."""

    def test_valid_model(self):
        """Test getting effort levels for valid model."""
        from config import get_effort_levels_for_model

        efforts = get_effort_levels_for_model("gpt-5-mini")
        assert efforts == ["minimal", "low", "medium", "high"]

    def test_invalid_model_returns_empty(self):
        """Test that invalid model returns empty list."""
        from config import get_effort_levels_for_model

        efforts = get_effort_levels_for_model("invalid-model")
        assert efforts == []


class TestModelsApiEndpoint:
    """Test GET /api/models endpoint."""

    @pytest.fixture
    def client(self, mock_csv_path, monkeypatch):
        """Create Flask test client."""
        monkeypatch.setenv("CSV_PATH", mock_csv_path)

        from app import app

        app.config["TESTING"] = True

        with app.test_client() as test_client:
            yield test_client

    def test_models_endpoint_returns_200(self, client):
        """Test that /api/models returns 200 OK."""
        response = client.get("/api/models")
        assert response.status_code == 200

    def test_models_endpoint_returns_expected_structure(self, client):
        """Test that /api/models returns correct structure."""
        response = client.get("/api/models")
        assert response.status_code == 200
        data = response.json

        assert "models" in data
        assert "available_models" in data
        assert "default_model" in data
        assert "default_effort" in data

    def test_models_endpoint_has_all_models(self, client):
        """Test that /api/models includes all expected models."""
        response = client.get("/api/models")
        data = response.json

        expected_models = ["gpt-5.2", "gpt-5.2-pro", "gpt-5-mini", "gpt-5-nano"]
        for model in expected_models:
            assert model in data["available_models"]
            assert model in data["models"]

    def test_models_endpoint_default_values(self, client):
        """Test that /api/models returns correct defaults."""
        response = client.get("/api/models")
        data = response.json

        assert data["default_model"] == "gpt-5-mini"
        assert data["default_effort"] == "low"
