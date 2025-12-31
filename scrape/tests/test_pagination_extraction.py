"""
Comprehensive pagination test for bike-components.de cassettes category.
This test verifies that:
1. Pagination extraction works with the sample HTML
2. Pagination test cases work for various page states
3. Integration with scraper works correctly
"""
import pytest
from pathlib import Path
from bs4 import BeautifulSoup
from scrape.html_utils import extract_next_page_url, extract_current_page


class TestPaginationExtraction:
    """Test pagination extraction with the cassettes sample HTML."""
    
    @pytest.fixture
    def sample_html_soup(self):
        """Load and parse the sample cassettes HTML."""
        html_path = Path(__file__).parent.parent.parent / "data/builder_input/cassettes_cat_bike-components.html"
        
        if not html_path.exists():
            pytest.skip(f"Sample HTML file not found: {html_path}")
        
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        return BeautifulSoup(html_content, "html.parser")

    @pytest.fixture
    def pedals_html_soup(self):
        """Load and parse the sample pedals HTML (no <link rel="next">)."""
        html_path = Path(__file__).parent.parent.parent / "data/builder_input/pedals_cat_bike-components.html"

        if not html_path.exists():
            pytest.skip(f"Sample pedals HTML file not found: {html_path}")

        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        return BeautifulSoup(html_content, "html.parser")
    
    def test_extract_next_page_from_cassettes_html(self, sample_html_soup):
        """Test extracting next page URL from the cassettes page (page 1)."""
        current_url = "https://www.bike-components.de/en/components/drivetrain/cassettes/"
        
        next_url = extract_next_page_url(sample_html_soup, current_url)
        
        # Should find the next page URL via <link rel="next">
        assert next_url is not None, "Should find next page URL"
        assert next_url == "https://www.bike-components.de/en/components/drivetrain/cassettes/?page=2"
    
    def test_extract_current_page_no_query(self):
        """Test extracting current page number when URL has no ?page parameter."""
        url = "https://www.bike-components.de/en/components/drivetrain/cassettes/"
        
        page_num = extract_current_page(url)
        
        assert page_num == 1, "Should default to page 1 when no page parameter"
    
    def test_extract_current_page_with_query(self):
        """Test extracting current page number from URL with ?page parameter."""
        url = "https://www.bike-components.de/en/components/drivetrain/cassettes/?page=3"
        
        page_num = extract_current_page(url)
        
        assert page_num == 3, "Should extract page number from URL"
    
    def test_pagination_with_link_rel_next_tag(self, sample_html_soup):
        """Test that <link rel=\"next\"> tag is properly detected."""
        # The cassettes HTML has a <link rel="next"> tag
        next_link = sample_html_soup.find("link", rel="next")
        
        assert next_link is not None, "<link rel=\"next\"> should be present"
        assert "page=2" in next_link.get("href", ""), "Next link should contain page=2"
    
    def test_pagination_with_navigation_div(self, sample_html_soup):
        """Test that page navigation divs are properly detected."""
        # Look for page-next navigation
        page_next_div = sample_html_soup.select_one('div.page-next')
        
        assert page_next_div is not None, "Should find <div class=\"page-next\">"
        
        # Find the link inside
        next_link = page_next_div.find('a')
        assert next_link is not None, "Should find link in page-next div"
        assert "page=2" in next_link.get("href", ""), "Link should point to page=2"

    def test_extract_next_page_without_rel_next(self, pedals_html_soup):
        """Pedals category has no <link rel="next">; ensure we still find next page."""
        current_url = "https://www.bike-components.de/en/components/drivetrain/pedals/"

        next_url = extract_next_page_url(pedals_html_soup, current_url)

        assert next_url is not None, "Should find next page even without rel=next"
        assert "page=2" in next_url, "Next page URL should include page=2"
    
    def test_extract_next_page_uses_link_rel_first(self, sample_html_soup):
        """Test that extract_next_page_url prioritizes <link rel=\"next\"> over other methods."""
        current_url = "https://www.bike-components.de/en/components/drivetrain/cassettes/"
        
        # Extract next URL
        next_url = extract_next_page_url(sample_html_soup, current_url)
        
        # Should use the <link rel="next"> tag
        assert next_url == "https://www.bike-components.de/en/components/drivetrain/cassettes/?page=2"
    
    def test_pagination_no_page_parameter_variation(self):
        """Test pagination with URLs that have other query parameters."""
        url_with_filter = "https://www.bike-components.de/en/components/drivetrain/cassettes/?filterManufacturer=shimano"
        
        page_num = extract_current_page(url_with_filter)
        
        # Should still default to page 1 when page param is missing
        assert page_num == 1


class TestPaginationEdgeCases:
    """Test edge cases for pagination extraction."""
    
    def test_extract_next_page_when_none_exists(self):
        """Test that extract_next_page_url returns None when no next page exists."""
        # Create minimal HTML with no pagination
        html = "<html><body><h1>Page</h1></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        
        next_url = extract_next_page_url(soup, "https://example.com/")
        
        assert next_url is None, "Should return None when no next page exists"
    
    def test_extract_current_page_invalid_format(self):
        """Test that extract_current_page handles invalid page numbers gracefully."""
        url = "https://example.com/?page=invalid"
        
        page_num = extract_current_page(url)
        
        assert page_num == 1, "Should default to 1 for invalid page numbers"
    
    def test_extract_current_page_multiple_page_params(self):
        """Test that extract_current_page uses the first page parameter."""
        # Note: This is an edge case - URLs shouldn't have multiple page params
        url = "https://example.com/?page=3&page=5"
        
        page_num = extract_current_page(url)
        
        # Should use the first value
        assert page_num == 3, "Should use first page parameter value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestPaginationWithScraper:
    """Test pagination in the context of the scraper workflow."""
    
    def test_pagination_flow_simulation(self):
        """Test simulating a multi-page pagination flow."""
        from scrape.html_utils import extract_next_page_url, extract_current_page
        
        # Simulate pages 1-3 of a category
        page_urls = [
            "https://www.bike-components.de/en/components/drivetrain/cassettes/",
            "https://www.bike-components.de/en/components/drivetrain/cassettes/?page=2",
            "https://www.bike-components.de/en/components/drivetrain/cassettes/?page=3",
            "https://www.bike-components.de/en/components/drivetrain/cassettes/?page=4",
        ]
        
        # Test page number extraction at each step
        for i, url in enumerate(page_urls, start=1):
            page_num = extract_current_page(url)
            assert page_num == i, f"Page {i} URL should extract page number {i}, got {page_num}"
    
    def test_pagination_url_consistency(self):
        """Test that pagination URLs are built consistently."""
        from scrape.html_utils import extract_current_page
        
        base_url = "https://www.bike-components.de/en/components/drivetrain/cassettes/"
        
        # Test URLs with various formats
        test_cases = [
            (base_url, 1),
            (base_url + "?page=2", 2),
            (base_url + "?page=10", 10),
            (base_url + "?filterManufacturer=shimano&page=3", 3),
        ]
        
        for url, expected_page in test_cases:
            page_num = extract_current_page(url)
            assert page_num == expected_page, f"URL {url} should extract page {expected_page}, got {page_num}"
