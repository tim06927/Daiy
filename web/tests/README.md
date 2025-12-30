# Test Suite Documentation

## Overview

This test suite validates the three-phase bike component recommendation flow:
1. **Job Identification** - Analyze user input to identify task, categories, and unclear specs
2. **Clarification** - Collect user answers for ambiguous specifications  
3. **Recommendation** - Match products and generate final instructions

## Test Structure

```
web/tests/
├── conftest.py                      # Shared fixtures and utilities
├── fixtures/
│   ├── example_prompts.json         # Test problem descriptions
│   └── images/                      # Test images (optional)
├── test_unit_data_structures.py     # Unit tests for JobIdentification, UnclearSpecification
├── test_api_endpoints.py            # Integration tests for API endpoints
├── test_error_handling.py           # Edge cases and error scenarios
├── test_model_clarification.py      # Vision API behavior (existing)
├── test_model_clarification_extended.py  # Gear counting tests (existing)
└── test_vision_flow.py              # End-to-end flow test (existing)
```

## Running Tests

### Install test dependencies
```bash
pip install pytest pytest-cov pytest-mock
```

### Run all tests
```bash
pytest web/tests/ -v
```

### Run specific test file
```bash
pytest web/tests/test_unit_data_structures.py -v
```

### Run specific test
```bash
pytest web/tests/test_unit_data_structures.py::TestUnclearSpecification::test_creation_basic -v
```

### Run with coverage
```bash
pytest web/tests/ --cov=web --cov-report=html --cov-report=term
```

### Run only unit tests (skip integration/API tests)
```bash
pytest web/tests/test_unit*.py -v
```

### Run only API tests
```bash
pytest web/tests/test_api*.py -v
```

## Test Categories

### Unit Tests

#### `test_unit_data_structures.py`
Tests for core data structures:
- **UnclearSpecification**: Creation, field validation, to_dict conversion
- **JobIdentification**: Creation, instruction handling, category extraction, serialization

**Key tests:**
- `test_creation_basic` - Basic object creation
- `test_referenced_categories_extraction` - Category extraction from instructions
- `test_to_dict` - Serialization and deserialization
- `test_confidence_boundary_values` - Boundary value testing

**Coverage:**
- Empty and populated fields
- Boundary values (0.0, 0.5, 1.0 confidence)
- Special characters and unicode
- Very long strings

### Integration Tests

#### `test_api_endpoints.py`
Tests for Flask API endpoints:
- **GET /api/categories** - Category list retrieval
- **POST /api/recommend** - Main recommendation endpoint

**Key tests:**
- `test_categories_endpoint_returns_list` - Validates endpoint returns categories
- `test_recommend_missing_problem_text` - Error handling for missing input
- `test_recommend_accepts_valid_inputs` - Valid input acceptance
- `test_recommend_with_clarification_answers` - Clarification flow

**Coverage:**
- Valid and invalid inputs
- Missing required fields
- Response format validation
- Content-type handling
- Clarification flow
- Image input handling

#### `test_error_handling.py`
Edge cases and error scenarios:
- Malformed input
- Type mismatches
- Boundary conditions
- Unicode and special characters
- Extremely long strings
- API error handling

**Key tests:**
- `test_extract_categories_with_malformed_brackets` - Malformed input handling
- `test_unclear_spec_with_very_long_strings` - Performance with large data
- `test_recommend_with_very_long_text` - API input validation
- `test_recommend_with_unicode_text` - Unicode handling

### Vision API Tests (Existing)

#### `test_model_clarification.py`
Tests OpenAI vision API behavior for clarification:
- Image analysis for gear counting
- Model comparison (gpt-5-mini vs gpt-5.2)
- Speed and use-case inference from images

#### `test_model_clarification_extended.py`
Direct gear-counting validation:
- Cog counting accuracy
- Bike type identification
- Brand/component detection

#### `test_vision_flow.py`
End-to-end integration test:
- Real bike photo analysis
- Full three-phase flow
- Grounding context building
- LLM recommendation generation

## Test Data

### Example Prompts (`fixtures/example_prompts.json`)

Provides realistic test scenarios:

```json
{
  "basic_chain_replacement": {
    "problem_text": "I need a new 12-speed chain for my road bike",
    "expected_categories": ["drivetrain_chains"],
    "expected_unclear_specs": []
  },
  "ambiguous_speed": {
    "problem_text": "I need to replace my cassette",
    "expected_categories": ["drivetrain_cassettes"],
    "expected_unclear_specs": ["gearing"]
  }
}
```

### Mock CSV Data

`conftest.py` creates temporary CSV files with sample products for testing:
- Shimano and KMC chains
- Shimano and SRAM cassettes
- Park Tool tools

## Fixtures

### Shared Fixtures (`conftest.py`)

- **`test_dir`** - Path to test directory
- **`fixtures_dir`** - Path to fixtures directory (auto-creates if missing)
- **`example_prompts`** - Loaded example prompts from JSON
- **`mock_openai_client`** - Mock OpenAI client
- **`mock_csv_path`** - Temporary CSV with sample products
- **`repo_root`** - Repository root directory
- **`sys_path_setup`** - Ensures proper Python path setup

### API Test Fixtures

- **`client`** - Flask test client with proper configuration

## Best Practices

### Writing Tests

1. **Clear naming**: `test_[function]_[scenario]`
   ```python
   def test_extract_categories_with_malformed_brackets():
   ```

2. **Docstrings**: Every test has a docstring explaining what it validates
   ```python
   def test_referenced_categories_extraction(self):
       """Test that category references are extracted from instructions."""
   ```

3. **Isolation**: Each test is independent
   - Use fixtures for setup
   - Clean up after tests
   - Don't depend on test execution order

4. **Parametrization**: Test multiple scenarios efficiently
   ```python
   @pytest.mark.parametrize("confidence", [0.0, 0.5, 1.0])
   def test_confidence_values(self, confidence):
   ```

5. **Assertions**: Clear and specific
   ```python
   assert job.confidence == 0.85  # ✓ Specific
   assert job  # ✗ Too vague
   ```

### Edge Cases to Test

- **Boundary values**: 0, max values, negative numbers
- **Empty inputs**: Empty lists, empty strings, None
- **Type mismatches**: Wrong type provided
- **Large data**: Very long strings, many items
- **Special characters**: Unicode, emoji, symbols
- **API errors**: Network failures, invalid responses

## Coverage Goals

Target areas for test improvement:

1. **Job Identification** (70% coverage)
   - LLM integration testing
   - Complex instruction generation
   - Category extraction accuracy

2. **Candidate Selection** (60% coverage)
   - Product filtering logic
   - Category validation
   - Price/brand filtering

3. **Recommendation Generation** (50% coverage)
   - Product ranking logic
   - Instruction finalization
   - JSON response generation

4. **Frontend Integration** (40% coverage)
   - Clarification UI rendering
   - Product display
   - Form submission

## Running Tests in CI/CD

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pip install pytest pytest-cov pytest-mock
    pytest web/tests/ --cov=web --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    files: ./coverage.xml
```

## Troubleshooting

### Tests fail with import errors
- Ensure `conftest.py` is in the tests directory
- Check `sys_path_setup` fixture is applied
- Verify web module structure is correct

### API tests fail with 500 errors
- Check CSV_PATH is set correctly
- Ensure mock products are in the right format
- Check Flask app configuration in fixture

### Vision API tests require OpenAI key
- Set `OPENAI_API_KEY` in `.env`
- Skip vision tests if key not available
- Use mocks for CI/CD environments

### Parametrized tests are too many
- Filter with `-k` option: `pytest -k "test_creation"`
- Mark slow tests: `@pytest.mark.slow`
- Run selectively: `pytest -m "not slow"`

## Next Steps

1. **Add missing test coverage**:
   - Candidate selection logic
   - Prompt building functions
   - Recommendation ranking

2. **Add integration tests**:
   - Full three-phase flow (job → clarification → recommendation)
   - Database interactions
   - File I/O operations

3. **Add performance tests**:
   - API response times
   - Large CSV handling
   - Image processing speed

4. **Add visual regression tests**:
   - Frontend UI rendering
   - Product card layouts
   - Responsive design

5. **Provide test data**:
   - Example problem texts
   - Sample bike photos
   - Expected output formats

## References

- [pytest documentation](https://docs.pytest.org/)
- [pytest fixtures](https://docs.pytest.org/en/stable/how-to-fixtures.html)
- [pytest parametrization](https://docs.pytest.org/en/stable/parametrize.html)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
