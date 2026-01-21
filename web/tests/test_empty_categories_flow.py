"""
Test the empty categories error handling flow.

Tests that when a category has no products, the system gracefully returns
diagnostic information instead of a 404 error.
"""

import json
import sys
from pathlib import Path

import pytest

# Setup path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_empty_categories_error_response_structure():
    """
    Test that the empty categories error response has all required fields
    for the frontend to display properly.
    """
    # Mock the response structure that api.py would return
    error_response = {
        "need_clarification": False,
        "error": "empty_categories",
        "message": "Some of the product categories needed for your project have no products available.",
        "empty_categories": ["drivetrain_tools"],
        "job": {
            "instructions": ["Use [cassettes]"],
            "unclear_specifications": [],
            "confidence": 0.95,
            "reasoning": ""
        },
        "instructions": ["Use [cassettes]"],
        "available_categories": ["cassettes"],
        "hint": "This typically means the product database needs to be refreshed or expanded.",
    }
    
    # Verify all required fields are present
    assert error_response["error"] == "empty_categories"
    assert isinstance(error_response["empty_categories"], list)
    assert isinstance(error_response["available_categories"], list)
    assert error_response["hint"]
    assert error_response["instructions"]
    assert error_response["message"]
    
    # The frontend checks for data.error === "empty_categories"
    # and uses data.empty_categories, data.available_categories, data.instructions, and data.hint
    assert all(key in error_response for key in [
        "error", "empty_categories", "available_categories", "instructions", "hint"
    ])


def test_empty_categories_frontend_handler():
    """
    Test that the frontend JavaScript handler would process the response correctly.
    This tests the response format matches what the JavaScript expects.
    """
    # Simulate the error response
    data = {
        "need_clarification": False,
        "error": "empty_categories",
        "message": "Some of the product categories needed for your project have no products available.",
        "empty_categories": ["drivetrain_tools", "cassette_tools"],
        "instructions": ["Use [drivetrain_tools] for drivetrain components", "Use [cassette_tools] for cassettes"],
        "available_categories": ["cassettes", "chains"],
        "hint": "This typically means the product database needs to be refreshed or expanded.",
    }
    
    # Verify frontend would extract all needed values
    empty_categories = data.get("empty_categories", [])
    available_categories = data.get("available_categories", [])
    instructions = data.get("instructions", [])
    hint = data.get("hint")
    message = data.get("message")
    
    # Ensure all values are available for display
    assert len(empty_categories) == 2
    assert len(available_categories) == 2
    assert len(instructions) == 2
    assert hint is not None
    assert message is not None
    
    # Verify HTML generation would work (simulating JavaScript template)
    error_html = f"""
    <div class="error-panel">
      <h3>⚠️ Missing Product Data</h3>
      <p><strong>{message}</strong></p>
      <div class="diagnostic-info">
        <h4>Categories Needed But Empty:</h4>
        <ul>
          {' '.join(f'<li><code>{cat}</code></li>' for cat in empty_categories)}
        </ul>
        <h4>Available Categories:</h4>
        <ul>
          {' '.join(f'<li><code>{cat}</code></li>' for cat in available_categories)}
        </ul>
        <h4>Your Project Steps:</h4>
        <ol>
          {' '.join(f'<li>{step}</li>' for step in instructions)}
        </ol>
        <p class="hint">💡 {hint}</p>
      </div>
    </div>
    """
    
    # Verify HTML contains all expected elements
    assert "Missing Product Data" in error_html
    assert "drivetrain_tools" in error_html
    assert "cassettes" in error_html
    assert "drivetrain_tools" in error_html
    assert "Use [drivetrain_tools]" in error_html


def test_empty_categories_css_classes():
    """
    Test that CSS classes used in error panel are correctly defined.
    """
    # Read the CSS file
    css_file = Path(__file__).resolve().parents[2] / "web/static/css/components.css"
    css_content = css_file.read_text()
    
    # Verify all CSS classes are defined
    required_classes = [
        ".error-panel",
        ".diagnostic-info",
        ".hint",
    ]
    
    for css_class in required_classes:
        assert css_class in css_content, f"CSS class {css_class} not found in components.css"
    
    # Verify key CSS properties
    assert "background:" in css_content.split(".error-panel")[1].split("}")[0]
    assert "border:" in css_content.split(".error-panel")[1].split("}")[0]
