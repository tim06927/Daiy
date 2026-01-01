"""Test API endpoints."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Setup path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def client(mock_csv_path, monkeypatch, repo_root):
    """Create Flask test client."""
    # Monkeypatch CSV path
    monkeypatch.setenv("CSV_PATH", mock_csv_path)
    
    # Create Flask app with test config
    from app import app
    app.config['TESTING'] = True

    with app.test_client() as test_client:
        yield test_client


class TestCategoriesEndpoint:
    """Test GET /api/categories endpoint."""

    def test_categories_endpoint_returns_200(self, client):
        """Test that /api/categories returns 200 OK."""
        response = client.get('/api/categories')
        assert response.status_code == 200

    def test_categories_endpoint_returns_list(self, client):
        """Test that /api/categories returns category list."""
        response = client.get('/api/categories')
        assert response.status_code == 200
        data = response.json
        assert 'categories' in data
        assert isinstance(data['categories'], list)

    def test_categories_have_required_fields(self, client):
        """Test that categories have all required fields."""
        response = client.get('/api/categories')
        categories = response.json.get('categories', [])

        if categories:
            for cat in categories:
                assert 'key' in cat, f"Category missing 'key': {cat}"
                assert 'display_name' in cat, f"Category missing 'display_name': {cat}"

    def test_categories_keys_are_strings(self, client):
        """Test that category keys are valid strings."""
        response = client.get('/api/categories')
        categories = response.json.get('categories', [])

        for cat in categories:
            assert isinstance(cat['key'], str)
            assert len(cat['key']) > 0


class TestRecommendEndpointBasics:
    """Test basic POST /api/recommend endpoint functionality."""

    def test_recommend_missing_problem_text(self, client):
        """Test that missing problem_text returns error."""
        response = client.post(
            '/api/recommend',
            json={},
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.json
        assert 'error' in data or 'message' in data

    def test_recommend_empty_problem_text(self, client):
        """Test with empty problem_text string."""
        response = client.post(
            '/api/recommend',
            json={"problem_text": ""},
            content_type='application/json'
        )
        # Should either return error or minimal response
        assert response.status_code in [400, 200]

    @pytest.mark.parametrize(
        "problem_text",
        [
            "I need a chain",
            "12-speed cassette replacement",
            "Help with drivetrain upgrade",
            "new drivetrain for gravel bike",
        ],
    )
    def test_recommend_accepts_valid_inputs(self, client, problem_text):
        """Test that valid inputs are accepted."""
        response = client.post(
            '/api/recommend',
            json={"problem_text": problem_text},
            content_type='application/json'
        )
        # Should return either 200 or 404, not 400
        assert response.status_code in [200, 404], f"Unexpected status {response.status_code} for: {problem_text}"

    def test_recommend_response_is_json(self, client):
        """Test that response is valid JSON."""
        response = client.post(
            '/api/recommend',
            json={"problem_text": "I need a chain"},
            content_type='application/json'
        )
        # Should be JSON parseable
        assert isinstance(response.json, dict)

    def test_recommend_with_image_base64(self, client):
        """Test accepting image as base64."""
        response = client.post(
            '/api/recommend',
            json={
                "problem_text": "What parts do I need?",
                "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
            },
            content_type='application/json'
        )
        assert response.status_code in [200, 400, 404]

    def test_recommend_with_invalid_json(self, client):
        """Test with invalid JSON in request."""
        response = client.post(
            '/api/recommend',
            data="not json",
            content_type='application/json'
        )
        assert response.status_code == 400


class TestRecommendEndpointClarification:
    """Test clarification flow in /api/recommend endpoint."""

    @patch('web.api.identify_job')
    def test_recommend_handles_clarification_response(self, mock_identify, client):
        """Test that endpoint handles cases needing clarification."""
        # Mock identify_job to return a job with unclear specs
        from web.job_identification import JobIdentification, UnclearSpecification
        
        unclear_spec = UnclearSpecification(
            spec_name="gearing",
            confidence=0.3,
            question="How many speeds?",
            hint="Count cogs",
            options=["10", "11", "12"],
        )
        
        job = JobIdentification(
            instructions=["Step 1: Check current setup"],
            unclear_specifications=[unclear_spec],
            confidence=0.7,
            reasoning="Speed not specified",
        )
        mock_identify.return_value = job

        response = client.post(
            '/api/recommend',
            json={"problem_text": "I need a cassette"},
            content_type='application/json'
        )

        # Should either indicate clarification needed or handle it internally
        assert response.status_code in [200, 400]

    def test_recommend_with_clarification_answers(self, client):
        """Test submitting clarification answers."""
        # This would ideally test the full clarification flow
        # Structure shown here - would need mocking for LLM calls
        response = client.post(
            '/api/recommend',
            json={
                "problem_text": "I need a cassette",
                "clarification_answers": [
                    {"spec_name": "gearing", "answer": "11"}
                ],
            },
            content_type='application/json'
        )
        # Should not crash
        assert response.status_code in [200, 400, 404]


class TestRecommendEndpointResponseFormat:
    """Test response format of /api/recommend endpoint."""

    def test_recommend_response_has_expected_fields(self, client):
        """Test that successful response has expected structure."""
        response = client.post(
            '/api/recommend',
            json={"problem_text": "I need a 12-speed chain for road bike"},
            content_type='application/json'
        )

        # Response should be JSON
        assert isinstance(response.json, dict)

        # Should have either clarification or results
        data = response.json
        if response.status_code == 200:
            # Either need_clarification or has results
            if 'need_clarification' in data:
                assert 'job' in data or 'clarifications' in data
            elif 'error' not in data:
                # Has results - check for result fields
                assert any(
                    k in data for k in ['final_instructions', 'sections', 'products', 'recommendations']
                ), f"Response missing expected result fields: {data.keys()}"

    def test_recommend_error_response_has_message(self, client):
        """Test that error responses have error message."""
        response = client.post(
            '/api/recommend',
            json={},
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.json
        assert 'error' in data or 'message' in data

    def test_recommend_response_no_unhandled_exceptions(self, client):
        """Test that endpoint handles all inputs without crashing."""
        test_inputs = [
            {"problem_text": "test"},
            {"problem_text": "test", "image_base64": "fake"},
            {"problem_text": "test", "clarification_answers": []},
        ]

        for test_input in test_inputs:
            response = client.post(
                '/api/recommend',
                json=test_input,
                content_type='application/json'
            )
            # Should not return 500
            assert response.status_code != 500, f"Got 500 error for input: {test_input}\nResponse: {response.json}"


class TestRecommendEndpointContentTypes:
    """Test content type handling."""

    def test_recommend_requires_json_content_type(self, client):
        """Test that non-JSON content type is handled."""
        response = client.post(
            '/api/recommend',
            data="problem_text=test",
            content_type='application/x-www-form-urlencoded'
        )
        # Should either accept it or return 400, not 500
        assert response.status_code != 500

    def test_recommend_json_response_content_type(self, client):
        """Test that response content type is JSON."""
        response = client.post(
            '/api/recommend',
            json={"problem_text": "test"},
            content_type='application/json'
        )
        assert 'application/json' in response.content_type
