"""Test privacy, consent, and data protection functionality."""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# Setup path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestRedactText:
    """Test text redaction functionality."""

    def test_redact_email_simple(self):
        """Test redacting a simple email address."""
        from privacy import redact_text
        
        result = redact_text("Contact me at john@example.com for help")
        assert "[REDACTED_EMAIL]" in result
        assert "john@example.com" not in result

    def test_redact_email_multiple(self):
        """Test redacting multiple email addresses."""
        from privacy import redact_text
        
        result = redact_text("Email john@example.com or jane@test.org")
        assert result.count("[REDACTED_EMAIL]") == 2
        assert "john@example.com" not in result
        assert "jane@test.org" not in result

    def test_redact_email_complex_domain(self):
        """Test redacting emails with complex domains."""
        from privacy import redact_text
        
        result = redact_text("Reach me at user.name+tag@company.co.uk")
        assert "[REDACTED_EMAIL]" in result

    def test_redact_phone_international(self):
        """Test redacting international phone numbers."""
        from privacy import redact_text
        
        result = redact_text("Call +49 123 456 7890 for support")
        assert "[REDACTED_PHONE]" in result
        assert "123 456 7890" not in result

    def test_redact_phone_us_format(self):
        """Test redacting US-style phone numbers."""
        from privacy import redact_text
        
        result = redact_text("Phone: (555) 123-4567")
        assert "[REDACTED_PHONE]" in result

    def test_redact_phone_simple(self):
        """Test redacting simple phone numbers."""
        from privacy import redact_text
        
        result = redact_text("Call 030-12345678")
        assert "[REDACTED_PHONE]" in result

    def test_no_redact_short_numbers(self):
        """Test that short numbers (like quantities) are not redacted."""
        from privacy import redact_text
        
        result = redact_text("I need 11 gears and 12 speeds")
        # These short numbers should NOT be redacted
        assert "11" in result
        assert "12" in result

    def test_no_redact_normal_text(self):
        """Test that normal text passes through unchanged."""
        from privacy import redact_text
        
        text = "I need a new chain for my bike"
        result = redact_text(text)
        assert result == text

    def test_redact_empty_string(self):
        """Test handling empty string."""
        from privacy import redact_text
        
        assert redact_text("") == ""

    def test_redact_none(self):
        """Test handling None input."""
        from privacy import redact_text
        
        assert redact_text(None) is None


class TestConsentRoutes:
    """Test consent and privacy routes."""

    @pytest.fixture
    def client(self, mock_csv_path, monkeypatch):
        """Create Flask test client without consent."""
        monkeypatch.setenv("CSV_PATH", mock_csv_path)
        from app import app
        
        app.config['TESTING'] = True
        with app.test_client() as test_client:
            yield test_client

    def test_consent_page_renders(self, client):
        """Test that consent page renders."""
        response = client.get('/consent')
        assert response.status_code == 200
        assert b'Alpha Demo' in response.data or b'alpha' in response.data.lower()

    def test_consent_redirects_from_home(self, client):
        """Test that home page redirects to consent when not consented."""
        response = client.get('/')
        assert response.status_code == 302
        assert '/consent' in response.headers.get('Location', '')

    def test_consent_redirects_from_api(self, client):
        """Test that API endpoints redirect to consent when not consented."""
        response = client.get('/api/categories')
        assert response.status_code == 302
        assert '/consent' in response.headers.get('Location', '')

    def test_privacy_page_no_consent_needed(self, client):
        """Test that privacy page doesn't require consent."""
        response = client.get('/privacy')
        assert response.status_code == 200
        assert b'Privacy' in response.data

    def test_robots_txt_no_consent_needed(self, client):
        """Test that robots.txt doesn't require consent."""
        response = client.get('/robots.txt')
        assert response.status_code == 200
        assert b'Disallow' in response.data

    def test_static_no_consent_needed(self, client):
        """Test that static files don't require consent."""
        response = client.get('/static/css/base.css')
        # Should either return the file or 404, not redirect to consent
        assert response.status_code in [200, 404]

    def test_consent_post_sets_session(self, client):
        """Test that posting consent sets session variables."""
        response = client.post('/consent', data={'consent': 'on'})
        assert response.status_code == 302  # Redirect after consent
        
        # Check session was set
        with client.session_transaction() as sess:
            assert sess.get('alpha_consent') is True
            assert sess.get('alpha_consent_ts') is not None

    def test_consent_post_without_checkbox_stays(self, client):
        """Test that posting without checkbox doesn't grant consent."""
        response = client.post('/consent', data={})
        # Should stay on consent page or redirect back
        assert response.status_code in [200, 302]

    def test_after_consent_home_works(self, client):
        """Test that home page works after consent."""
        # Grant consent
        client.post('/consent', data={'consent': 'on'})
        
        # Now home should work
        response = client.get('/')
        assert response.status_code == 200

    def test_after_consent_api_works(self, client):
        """Test that API works after consent."""
        # Grant consent
        client.post('/consent', data={'consent': 'on'})
        
        # Now API should work
        response = client.get('/api/categories')
        assert response.status_code == 200


class TestRobotsTxt:
    """Test robots.txt content."""

    @pytest.fixture
    def client(self, mock_csv_path, monkeypatch):
        """Create Flask test client."""
        monkeypatch.setenv("CSV_PATH", mock_csv_path)
        from app import app
        
        app.config['TESTING'] = True
        with app.test_client() as test_client:
            yield test_client

    def test_robots_txt_disallows_all(self, client):
        """Test that robots.txt disallows all crawling."""
        response = client.get('/robots.txt')
        assert response.status_code == 200
        content = response.data.decode('utf-8')
        assert 'User-agent: *' in content
        assert 'Disallow: /' in content

    def test_robots_txt_plain_text(self, client):
        """Test that robots.txt is plain text."""
        response = client.get('/robots.txt')
        assert 'text/plain' in response.content_type


class TestPrivacyPage:
    """Test privacy page content."""

    @pytest.fixture
    def client(self, mock_csv_path, monkeypatch):
        """Create Flask test client."""
        monkeypatch.setenv("CSV_PATH", mock_csv_path)
        from app import app
        
        app.config['TESTING'] = True
        with app.test_client() as test_client:
            yield test_client

    def test_privacy_page_has_required_sections(self, client):
        """Test that privacy page contains required information."""
        response = client.get('/privacy')
        content = response.data.decode('utf-8')
        
        # Check for key required content
        assert 'DAIY' in content or 'Controller' in content
        assert 'hello@daiy.de' in content
        assert '90' in content  # Retention period
        assert 'OpenAI' in content

    def test_privacy_page_has_noindex(self, client):
        """Test that privacy page has noindex meta tag."""
        response = client.get('/privacy')
        content = response.data.decode('utf-8')
        
        assert 'noindex' in content.lower()


class TestHealthEndpoint:
    """Test health check endpoint."""

    @pytest.fixture
    def client(self, mock_csv_path, monkeypatch):
        """Create Flask test client."""
        monkeypatch.setenv("CSV_PATH", mock_csv_path)
        from app import app
        
        app.config['TESTING'] = True
        with app.test_client() as test_client:
            yield test_client

    def test_health_endpoint_works(self, client):
        """Test that health endpoint returns ok without consent."""
        response = client.get('/health')
        assert response.status_code == 200
        assert b'ok' in response.data
