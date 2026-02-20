# Testing Guide

## Setup

### 1. Install Testing Dependencies

```bash
pip install -r requirements-test.txt
```

This installs:
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
- `httpx` - HTTP client for testing
- `requests` - For manual testing script

### 2. Generate Test PDF Files

```bash
python tests/generate_test_pdfs.py
```

This creates various test PDFs in `tests/test_data/`:
- `valid_1_page.pdf` - Single page
- `valid_5_pages.pdf` - 5 pages
- `valid_10_pages.pdf` - 10 pages
- `valid_100_pages.pdf` - 100 pages
- `medium_valid.pdf` - ~5MB file
- `corrupted.pdf` - Broken PDF
- `encrypted.pdf` - Password-protected
- `fake.pdf` - Text file with .pdf extension
- `empty.pdf` - Empty file

---

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Unit Tests Only

```bash
pytest tests/unit/
```

### Run Integration Tests Only

```bash
pytest tests/integration/
```

### Run Specific Test File

```bash
pytest tests/unit/test_validator.py
```

### Run Specific Test

```bash
pytest tests/unit/test_validator.py::TestSizeCheck::test_small_file_allowed
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Coverage

```bash
pip install pytest-cov
pytest --cov=modules --cov=utils --cov-report=html
```

---

## Manual Testing

### Interactive Testing Script

```bash
python tests/manual_test.py
```

This provides an interactive menu for:
1. Health checks
2. Size validation
3. Upload & process PDFs
4. Error case testing
5. Full workflow testing
6. Custom PDF testing

### Manual API Testing with cURL

#### 1. Check Size
```bash
curl -X POST http://localhost:8000/api/check-size \
  -H "Content-Type: application/json" \
  -d '{"file_size": 1048576}'
```

#### 2. Upload PDF
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@tests/test_data/valid_1_page.pdf" \
  -F "chunk_size=5"
```

#### 3. Check Status
```bash
curl http://localhost:8000/api/status/{job_id}
```

#### 4. Download Result
```bash
curl -O http://localhost:8000/api/download/{job_id}
```

#### 5. Cleanup
```bash
curl -X DELETE http://localhost:8000/api/cleanup/{job_id}
```

---

## Test Coverage

### Unit Tests

**Validator Module** (`test_validator.py`):
- ✅ Size checking (small, large, zero, negative)
- ✅ PDF validation (valid, corrupted, encrypted, fake, empty)
- ✅ Byte formatting
- ✅ ValidationResult class

**Processor Module** (`test_processor.py`):
- ✅ PDF splitting (various chunk sizes)
- ✅ Chunk ordering
- ✅ Color assignment
- ✅ PDF merging
- ✅ ChunkInfo dataclass

**Watermark Module** (`test_watermark.py`):
- ✅ Watermark overlay creation
- ✅ Watermark application
- ✅ Custom settings
- ✅ Color selection and rotation

**Status Manager** (`test_status_manager.py`):
- ✅ Job creation and tracking
- ✅ Status updates
- ✅ Progress tracking
- ✅ Job cleanup
- ✅ Thread safety

### Integration Tests

**API Endpoints** (`test_api_endpoints.py`):
- ✅ Health checks
- ✅ Size check endpoint
- ✅ Upload endpoint (valid/invalid files)
- ✅ Status endpoint
- ✅ Download endpoint
- ✅ Cleanup endpoint
- ✅ Admin endpoints
- ✅ Full workflow tests

---

## Test Data Files

All test PDFs are in `tests/test_data/`:

| File | Description | Size |
|------|-------------|------|
| `valid_1_page.pdf` | Single page | ~3 KB |
| `valid_5_pages.pdf` | 5 pages | ~15 KB |
| `valid_10_pages.pdf` | 10 pages | ~30 KB |
| `valid_100_pages.pdf` | 100 pages | ~300 KB |
| `medium_valid.pdf` | Large file | ~5 MB |
| `corrupted.pdf` | Truncated PDF | Variable |
| `encrypted.pdf` | Password-protected | ~3 KB |
| `fake.pdf` | Text file | ~100 B |
| `empty.pdf` | Empty file | 0 B |

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      - name: Generate test PDFs
        run: python tests/generate_test_pdfs.py
      - name: Run tests
        run: pytest -v
```

---

## Troubleshooting

### Tests Fail with "Module not found"

Make sure you're in the project root directory:
```bash
cd WaterMarks-backend
pytest
```

### Test PDFs Missing

Generate them:
```bash
python tests/generate_test_pdfs.py
```

### Server Not Running (Integration Tests)

Start the server first:
```bash
python app.py &
pytest tests/integration/
```

Or use the test client (no need to start server):
```bash
pytest tests/integration/  # Uses TestClient automatically
```

### Import Errors

Ensure the project structure is correct and you have `__init__.py` files in all directories.

---

## Performance Testing

For performance testing, you can use the manual testing script with large PDFs:

```bash
# Time a 100-page PDF with small chunks
time python -c "
import requests
with open('tests/test_data/valid_100_pages.pdf', 'rb') as f:
    r = requests.post('http://localhost:8000/api/upload',
                     files={'file': f},
                     data={'chunk_size': 10})
    print(r.json())
"
```

---

## Writing New Tests

### Unit Test Template

```python
import pytest
from modules.your_module import your_function

class TestYourFeature:
    def test_basic_case(self):
        result = your_function(input_data)
        assert result == expected_output
    
    def test_edge_case(self):
        with pytest.raises(Exception):
            your_function(invalid_input)
```

### Integration Test Template

```python
def test_endpoint(client):
    response = client.get("/your-endpoint")
    assert response.status_code == 200
    assert "expected_key" in response.json()
```

---

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [PyPDF2 documentation](https://pypdf2.readthedocs.io/)
