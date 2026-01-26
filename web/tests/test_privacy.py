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

    def test_consent_preserves_next_url_on_form_rerender(self, client):
        """Test that the next URL is preserved when form is re-rendered (without checkbox).
        
        This is a regression test for the issue where POSTing the consent form
        without the checkbox would lose the next URL, causing the page to reload
        with next="/" instead of the original destination.
        """
        # POST to consent with a next URL but without checking the box
        response = client.post('/consent', data={'next': '/api/categories'})
        
        # Should re-render the form (200) with the next URL preserved
        assert response.status_code == 200
        content = response.data.decode('utf-8')
        
        # The hidden input field should still have the original next URL
        assert 'value="/api/categories"' in content
        # Make sure it didn't default to "/"
        assert 'value="/"' not in content or '/api/categories' in content

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

    def test_consent_page_has_back_button(self, client):
        """Test that consent page has a Back button."""
        response = client.get('/consent')
        assert response.status_code == 200
        content = response.data.decode('utf-8')
        # Check for Back button
        assert 'id="back-btn"' in content
        assert 'Back' in content

    def test_consent_page_has_continue_button(self, client):
        """Test that consent page has a Continue button."""
        response = client.get('/consent')
        assert response.status_code == 200
        content = response.data.decode('utf-8')
        # Check for Continue button
        assert 'id="continue-btn"' in content
        assert 'Continue' in content

    def test_consent_page_has_checkbox_validation_script(self, client):
        """Test that consent page has JavaScript for checkbox validation."""
        response = client.get('/consent')
        assert response.status_code == 200
        content = response.data.decode('utf-8')
        # Check for checkbox validation script
        assert 'checkbox.addEventListener' in content or 'continueBtn.disabled' in content

    def test_consent_page_has_back_button_script(self, client):
        """Test that consent page has JavaScript for back button."""
        response = client.get('/consent')
        assert response.status_code == 200
        content = response.data.decode('utf-8')
        # Check for back button script
        assert 'window.history.back' in content or "history.back()" in content


class TestUrlValidationHelpers:
    """Test URL validation helper functions directly."""

    def test_is_safe_redirect_url_rejects_external_https(self):
        """Test that _is_safe_redirect_url rejects HTTPS URLs."""
        from app import _is_safe_redirect_url
        assert _is_safe_redirect_url('https://evil.com') is False

    def test_is_safe_redirect_url_rejects_external_http(self):
        """Test that _is_safe_redirect_url rejects HTTP URLs."""
        from app import _is_safe_redirect_url
        assert _is_safe_redirect_url('http://evil.com') is False

    def test_is_safe_redirect_url_rejects_javascript(self):
        """Test that _is_safe_redirect_url rejects javascript: URLs."""
        from app import _is_safe_redirect_url
        assert _is_safe_redirect_url('javascript:alert(1)') is False

    def test_is_safe_redirect_url_rejects_data(self):
        """Test that _is_safe_redirect_url rejects data: URLs."""
        from app import _is_safe_redirect_url
        assert _is_safe_redirect_url('data:text/html,<script>') is False

    def test_is_safe_redirect_url_rejects_protocol_relative(self):
        """Test that _is_safe_redirect_url rejects protocol-relative URLs."""
        from app import _is_safe_redirect_url
        assert _is_safe_redirect_url('//evil.com') is False
        assert _is_safe_redirect_url('//evil.com/path') is False

    def test_is_safe_redirect_url_rejects_backslash_variants(self):
        """Test that _is_safe_redirect_url rejects backslash URL variants."""
        from app import _is_safe_redirect_url
        assert _is_safe_redirect_url('/\\evil.com') is False
        assert _is_safe_redirect_url('\\/evil.com') is False

    def test_is_safe_redirect_url_rejects_no_leading_slash(self):
        """Test that _is_safe_redirect_url rejects URLs without leading slash."""
        from app import _is_safe_redirect_url
        assert _is_safe_redirect_url('evil.com') is False
        assert _is_safe_redirect_url('path/to/page') is False

    def test_is_safe_redirect_url_rejects_empty(self):
        """Test that _is_safe_redirect_url rejects empty strings."""
        from app import _is_safe_redirect_url
        assert _is_safe_redirect_url('') is False
        assert _is_safe_redirect_url(None) is False

    def test_is_safe_redirect_url_accepts_root(self):
        """Test that _is_safe_redirect_url accepts root path."""
        from app import _is_safe_redirect_url
        assert _is_safe_redirect_url('/') is True

    def test_is_safe_redirect_url_accepts_internal_path(self):
        """Test that _is_safe_redirect_url accepts internal paths."""
        from app import _is_safe_redirect_url
        assert _is_safe_redirect_url('/search') is True
        assert _is_safe_redirect_url('/api/categories') is True

    def test_is_safe_redirect_url_accepts_path_with_query(self):
        """Test that _is_safe_redirect_url accepts paths with query strings."""
        from app import _is_safe_redirect_url
        assert _is_safe_redirect_url('/search?q=test') is True
        assert _is_safe_redirect_url('/search?q=test&filter=active') is True

    def test_is_safe_redirect_url_accepts_path_with_fragment(self):
        """Test that _is_safe_redirect_url accepts paths with fragments."""
        from app import _is_safe_redirect_url
        assert _is_safe_redirect_url('/search#results') is True
        assert _is_safe_redirect_url('/search?q=test#results') is True

    def test_is_safe_redirect_url_whitespace_handling_safe_paths(self):
        """Test that URLs with leading/trailing whitespace are normalized for safe paths."""
        from app import _is_safe_redirect_url
        # Safe paths with whitespace should be accepted after normalization
        assert _is_safe_redirect_url('  /path  ') is True
        assert _is_safe_redirect_url('  /search?q=test  ') is True
        assert _is_safe_redirect_url('\t/api/categories\t') is True
        assert _is_safe_redirect_url('  /  ') is True

    def test_is_safe_redirect_url_whitespace_handling_unsafe_urls(self):
        """Test that URLs with leading/trailing whitespace are rejected for unsafe URLs."""
        from app import _is_safe_redirect_url
        # Unsafe URLs with whitespace should still be rejected after normalization
        assert _is_safe_redirect_url('  https://evil.com  ') is False
        assert _is_safe_redirect_url('  //evil.com  ') is False
        assert _is_safe_redirect_url('\t//evil.com/path\t') is False
        assert _is_safe_redirect_url('  javascript:alert(1)  ') is False

    def test_is_safe_redirect_url_whitespace_only(self):
        """Test that whitespace-only strings are rejected."""
        from app import _is_safe_redirect_url
        assert _is_safe_redirect_url('   ') is False
        assert _is_safe_redirect_url('\t\t') is False
        assert _is_safe_redirect_url('\n\n') is False

    def test_is_safe_redirect_url_malformed_schemes_single_slash(self):
        """Test that malformed schemes with single slash are rejected."""
        from app import _is_safe_redirect_url
        # These are malformed URLs that might bypass naive URL parsers
        assert _is_safe_redirect_url('https:/example.com') is False
        assert _is_safe_redirect_url('http:/example.com') is False
        assert _is_safe_redirect_url('ftp:/example.com') is False
        assert _is_safe_redirect_url('file:/etc/passwd') is False

    def test_is_safe_redirect_url_malformed_schemes_triple_slash(self):
        """Test that malformed schemes with triple slash are rejected."""
        from app import _is_safe_redirect_url
        assert _is_safe_redirect_url('https:///example.com') is False
        assert _is_safe_redirect_url('http:///example.com') is False

    def test_is_safe_redirect_url_mixed_backslash_forward_slash_schemes(self):
        """Test that mixed backslash/forward slash schemes are rejected."""
        from app import _is_safe_redirect_url
        # These use backslashes which get normalized to forward slashes
        assert _is_safe_redirect_url('https:\\example.com') is False
        assert _is_safe_redirect_url('http:\\example.com') is False
        assert _is_safe_redirect_url('https:\\/example.com') is False
        assert _is_safe_redirect_url('http:/\\example.com') is False

    def test_is_safe_redirect_url_double_backslash_urls(self):
        """Test that double backslash URLs are rejected."""
        from app import _is_safe_redirect_url
        # Double backslash gets normalized to double forward slash (protocol-relative)
        assert _is_safe_redirect_url('\\\\example.com') is False
        assert _is_safe_redirect_url('\\\\example.com/path') is False
        assert _is_safe_redirect_url('\\\\evil.com?query=value') is False

    def test_get_safe_redirect_url_returns_valid_url(self):
        """Test that _get_safe_redirect_url returns valid URLs."""
        from app import _get_safe_redirect_url
        assert _get_safe_redirect_url('/search') == '/search'
        assert _get_safe_redirect_url('/api/categories') == '/api/categories'

    def test_get_safe_redirect_url_returns_default_for_invalid(self):
        """Test that _get_safe_redirect_url returns default for invalid URLs."""
        from app import _get_safe_redirect_url
        assert _get_safe_redirect_url('https://evil.com') == '/'
        assert _get_safe_redirect_url('//evil.com') == '/'
        assert _get_safe_redirect_url('javascript:alert(1)') == '/'

    def test_get_safe_redirect_url_custom_default(self):
        """Test that _get_safe_redirect_url accepts custom default."""
        from app import _get_safe_redirect_url
        assert _get_safe_redirect_url('https://evil.com', '/home') == '/home'
        assert _get_safe_redirect_url(None, '/home') == '/home'


class TestUrlSecurityOpenRedirect:
    """Test protection against open redirect attacks."""

    @pytest.fixture
    def client(self, mock_csv_path, monkeypatch):
        """Create Flask test client without consent."""
        monkeypatch.setenv("CSV_PATH", mock_csv_path)
        from app import app

        app.config['TESTING'] = True
        with app.test_client() as test_client:
            yield test_client

    def test_rejects_external_url_in_next(self, client):
        """Test that external URLs in 'next' parameter are rejected."""
        # Try to redirect to external site
        response = client.post('/consent', data={
            'consent': 'on',
            'next': 'https://evil.com'
        })
        assert response.status_code == 302
        # Should redirect to home, not to evil.com
        assert 'evil.com' not in response.headers.get('Location', '')
        assert response.headers.get('Location', '').endswith('/')

    def test_rejects_protocol_relative_url(self, client):
        """Test that protocol-relative URLs are rejected."""
        response = client.post('/consent', data={
            'consent': 'on',
            'next': '//evil.com/path'
        })
        assert response.status_code == 302
        assert 'evil.com' not in response.headers.get('Location', '')

    def test_rejects_javascript_url(self, client):
        """Test that javascript: URLs are rejected."""
        response = client.post('/consent', data={
            'consent': 'on',
            'next': 'javascript:alert(1)'
        })
        assert response.status_code == 302
        assert 'javascript' not in response.headers.get('Location', '')

    def test_allows_valid_internal_path(self, client):
        """Test that valid internal paths are allowed."""
        response = client.post('/consent', data={
            'consent': 'on',
            'next': '/api/categories'
        })
        assert response.status_code == 302
        assert '/api/categories' in response.headers.get('Location', '')

    def test_allows_internal_path_with_query(self, client):
        """Test that internal paths with query strings are allowed."""
        response = client.post('/consent', data={
            'consent': 'on',
            'next': '/search?q=test'
        })
        assert response.status_code == 302
        assert '/search?q=test' in response.headers.get('Location', '')

    def test_get_consent_sanitizes_next_url(self, client):
        """Test that GET /consent sanitizes the next URL too."""
        response = client.get('/consent?next=https://evil.com')
        assert response.status_code == 200
        # The page should not contain the malicious URL
        content = response.data.decode('utf-8')
        assert 'evil.com' not in content

    def test_rejects_data_url(self, client):
        """Test that data: URLs are rejected."""
        response = client.post('/consent', data={
            'consent': 'on',
            'next': 'data:text/html,<script>alert(1)</script>'
        })
        assert response.status_code == 302
        assert 'data:' not in response.headers.get('Location', '')
        assert response.headers.get('Location', '').endswith('/')

    def test_rejects_file_url(self, client):
        """Test that file: URLs are rejected."""
        response = client.post('/consent', data={
            'consent': 'on',
            'next': 'file:///etc/passwd'
        })
        assert response.status_code == 302
        assert 'file:' not in response.headers.get('Location', '')
        assert response.headers.get('Location', '').endswith('/')

    def test_rejects_backslash_slash_url(self, client):
        """Test that backslash-slash URLs are rejected."""
        response = client.post('/consent', data={
            'consent': 'on',
            'next': '/\\evil.com'
        })
        assert response.status_code == 302
        assert 'evil.com' not in response.headers.get('Location', '')

    def test_rejects_slash_backslash_url(self, client):
        """Test that slash-backslash URLs are rejected."""
        response = client.post('/consent', data={
            'consent': 'on',
            'next': '\\/evil.com'
        })
        assert response.status_code == 302
        assert 'evil.com' not in response.headers.get('Location', '')

    def test_rejects_url_without_leading_slash(self, client):
        """Test that URLs without leading slash are rejected."""
        response = client.post('/consent', data={
            'consent': 'on',
            'next': 'evil.com'
        })
        assert response.status_code == 302
        assert 'evil.com' not in response.headers.get('Location', '')
        assert response.headers.get('Location', '').endswith('/')

    def test_rejects_empty_next_parameter(self, client):
        """Test that empty next parameter defaults to home."""
        response = client.post('/consent', data={
            'consent': 'on',
            'next': ''
        })
        assert response.status_code == 302
        assert response.headers.get('Location', '').endswith('/')

    def test_allows_internal_path_with_fragment(self, client):
        """Test that internal paths with fragments are allowed."""
        response = client.post('/consent', data={
            'consent': 'on',
            'next': '/search#results'
        })
        assert response.status_code == 302
        assert '/search#results' in response.headers.get('Location', '')

    def test_allows_internal_path_with_query_and_fragment(self, client):
        """Test that internal paths with query and fragment are allowed."""
        response = client.post('/consent', data={
            'consent': 'on',
            'next': '/search?q=bike#results'
        })
        assert response.status_code == 302
        assert '/search?q=bike#results' in response.headers.get('Location', '')

    def test_rejects_url_encoded_external_url(self, client):
        """Test that URL-encoded external URLs are rejected."""
        # %2F%2F encodes //
        response = client.post('/consent', data={
            'consent': 'on',
            'next': '%2F%2Fevil.com'
        })
        assert response.status_code == 302
        # Should reject because it doesn't start with /
        assert 'evil.com' not in response.headers.get('Location', '')

    def test_consent_redirect_from_query_string(self, client):
        """Test that consent redirect works from query string (GET request)."""
        # First, visit consent page with next in query string
        response = client.get('/consent?next=/api/categories')
        assert response.status_code == 200
        content = response.data.decode('utf-8')
        # Check that the hidden field contains the next URL
        assert 'value="/api/categories"' in content
        
        # Now POST consent with the next URL preserved
        response = client.post('/consent', data={
            'consent': 'on',
            'next': '/api/categories'
        })
        assert response.status_code == 302
        assert '/api/categories' in response.headers.get('Location', '')

    def test_consent_redirect_from_form_data(self, client):
        """Test that consent redirect works from form data (POST request)."""
        response = client.post('/consent', data={
            'consent': 'on',
            'next': '/search?q=test'
        })
        assert response.status_code == 302
        assert '/search?q=test' in response.headers.get('Location', '')


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
