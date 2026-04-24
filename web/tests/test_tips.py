"""Tests for the /api/tips endpoint."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Setup path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def client(mock_csv_path, monkeypatch, repo_root):
    """Create Flask test client with consent already granted."""
    monkeypatch.setenv("CSV_PATH", mock_csv_path)

    from app import app
    app.config['TESTING'] = True

    with app.test_client() as test_client:
        with test_client.session_transaction() as sess:
            sess['alpha_consent'] = True
            sess['alpha_consent_ts'] = '2025-01-01T00:00:00+00:00'
        yield test_client


class TestTipsEndpoint:
    """Test POST /api/tips endpoint."""

    def test_tips_returns_200_on_empty_body(self, client):
        """Tips gracefully returns empty list when no problem_text supplied."""
        resp = client.post('/api/tips', json={})
        assert resp.status_code == 200
        assert resp.json == {"tips": []}

    def test_tips_returns_200_on_missing_text(self, client):
        """Tips returns empty when problem_text is blank."""
        resp = client.post('/api/tips', json={"problem_text": ""})
        assert resp.status_code == 200
        assert resp.json == {"tips": []}

    def test_tips_returns_200_on_non_string_text(self, client):
        """Tips returns empty when problem_text is not a string."""
        resp = client.post('/api/tips', json={"problem_text": 42})
        assert resp.status_code == 200
        assert resp.json == {"tips": []}

    @patch("openai.OpenAI")
    def test_tips_returns_list_on_success(self, mock_openai_cls, client):
        """Tips returns a list of strings when the LLM responds correctly."""
        mock_tips = [
            "Always degrease your chain before installing a new one.",
            "Use a torque wrench for cassette lockring.",
            "Check chain length against the old chain.",
        ]
        # Set up mock response
        mock_content = MagicMock()
        mock_content.text = json.dumps(mock_tips)
        mock_item = MagicMock()
        mock_item.content = [mock_content]
        mock_resp = MagicMock()
        mock_resp.output = [mock_item]
        mock_openai_cls.return_value.responses.create.return_value = mock_resp

        resp = client.post(
            '/api/tips',
            json={"problem_text": "My chain is worn out"},
        )
        assert resp.status_code == 200
        data = resp.json
        assert "tips" in data
        assert isinstance(data["tips"], list)
        assert len(data["tips"]) == 3
        assert data["tips"][0] == mock_tips[0]

    @patch("openai.OpenAI")
    def test_tips_handles_llm_failure_gracefully(self, mock_openai_cls, client):
        """Tips returns empty list when LLM call throws."""
        mock_openai_cls.return_value.responses.create.side_effect = RuntimeError("API down")

        resp = client.post(
            '/api/tips',
            json={"problem_text": "Need a new cassette"},
        )
        assert resp.status_code == 200
        assert resp.json == {"tips": []}

    @patch("openai.OpenAI")
    def test_tips_handles_invalid_json_from_llm(self, mock_openai_cls, client):
        """Tips returns empty list when LLM returns non-JSON."""
        mock_content = MagicMock()
        mock_content.text = "This is not JSON"
        mock_item = MagicMock()
        mock_item.content = [mock_content]
        mock_resp = MagicMock()
        mock_resp.output = [mock_item]
        mock_openai_cls.return_value.responses.create.return_value = mock_resp

        resp = client.post(
            '/api/tips',
            json={"problem_text": "Brake pads worn"},
        )
        assert resp.status_code == 200
        assert resp.json == {"tips": []}

    @patch("openai.OpenAI")
    def test_tips_caps_at_max_count(self, mock_openai_cls, client):
        """Tips are capped at TIPS_MAX_COUNT."""
        from config import TIPS_MAX_COUNT

        long_list = [f"Tip {i}" for i in range(20)]
        mock_content = MagicMock()
        mock_content.text = json.dumps(long_list)
        mock_item = MagicMock()
        mock_item.content = [mock_content]
        mock_resp = MagicMock()
        mock_resp.output = [mock_item]
        mock_openai_cls.return_value.responses.create.return_value = mock_resp

        resp = client.post(
            '/api/tips',
            json={"problem_text": "General maintenance question"},
        )
        assert resp.status_code == 200
        assert len(resp.json["tips"]) <= TIPS_MAX_COUNT

    @patch("openai.OpenAI")
    def test_tips_uses_fast_model(self, mock_openai_cls, client):
        """Tips endpoint uses the fastest model from config."""
        from config import TIPS_MODEL, TIPS_EFFORT

        mock_content = MagicMock()
        mock_content.text = '["Tip 1"]'
        mock_item = MagicMock()
        mock_item.content = [mock_content]
        mock_resp = MagicMock()
        mock_resp.output = [mock_item]
        mock_openai_cls.return_value.responses.create.return_value = mock_resp

        client.post(
            '/api/tips',
            json={"problem_text": "Chain replacement"},
        )

        call_kwargs = mock_openai_cls.return_value.responses.create.call_args
        assert call_kwargs.kwargs["model"] == TIPS_MODEL
        assert call_kwargs.kwargs["reasoning"] == {"effort": TIPS_EFFORT}
