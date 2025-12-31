"""Shared test fixtures and utilities for the web test suite."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def test_dir():
    """Return path to test directory."""
    return Path(__file__).parent


@pytest.fixture
def fixtures_dir(test_dir):
    """Return path to fixtures directory."""
    fixtures = test_dir / "fixtures"
    fixtures.mkdir(exist_ok=True)
    return fixtures


@pytest.fixture
def example_prompts(fixtures_dir):
    """Load example problem descriptions."""
    prompts_file = fixtures_dir / "example_prompts.json"
    
    # Create default prompts if file doesn't exist
    default_prompts = {
        "basic_chain_replacement": {
            "problem_text": "I need a new 12-speed chain for my road bike",
            "expected_categories": ["drivetrain_chains"],
            "expected_unclear_specs": []
        },
        "ambiguous_speed": {
            "problem_text": "I need to replace my cassette",
            "expected_categories": ["drivetrain_cassettes"],
            "expected_unclear_specs": ["gearing"]
        },
        "complex_upgrade": {
            "problem_text": "I want to upgrade my gravel bike drivetrain for better climbing",
            "expected_categories": ["drivetrain_cassettes", "drivetrain_chains"],
            "expected_unclear_specs": ["gearing"]
        }
    }
    
    if not prompts_file.exists():
        prompts_file.write_text(json.dumps(default_prompts, indent=2))
    
    with open(prompts_file) as f:
        return json.load(f)


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client for testing without API calls."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_csv_path(tmp_path):
    """Create a temporary CSV with sample products."""
    csv_content = """category,name,brand,price_text,url
drivetrain_chains,Shimano CN-M8100,Shimano,29.99€,https://example.com/chain1
drivetrain_chains,KMC X11,KMC,24.99€,https://example.com/chain2
drivetrain_cassettes,Shimano CS-HG700-11,Shimano,44.99€,https://example.com/cassette1
drivetrain_cassettes,SRAM XG-1150,SRAM,54.99€,https://example.com/cassette2
drivetrain_tools,Park Tool CT-3.2,Park Tool,19.99€,https://example.com/tool1
"""
    csv_file = tmp_path / "test_products.csv"
    csv_file.write_text(csv_content)
    return str(csv_file)


@pytest.fixture
def repo_root():
    """Get the repository root directory."""
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def sys_path_setup(repo_root):
    """Ensure repo_root and web directories are in sys.path."""
    web_dir = repo_root / "web"
    for p in (repo_root, web_dir):
        p_str = str(p)
        if p_str not in sys.path:
            sys.path.insert(0, p_str)
    yield
    # Cleanup
    for p in (repo_root, web_dir):
        p_str = str(p)
        if p_str in sys.path:
            sys.path.remove(p_str)
