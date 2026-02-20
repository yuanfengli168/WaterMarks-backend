"""
Pytest configuration and fixtures
"""
import pytest
import os
import sys
from fastapi.testclient import TestClient

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
import config


@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def test_data_dir():
    """Path to test data directory"""
    return os.path.join(os.path.dirname(__file__), "test_data")


@pytest.fixture
def valid_pdf_1_page(test_data_dir):
    """Path to valid 1-page PDF"""
    return os.path.join(test_data_dir, "valid_1_page.pdf")


@pytest.fixture
def valid_pdf_5_pages(test_data_dir):
    """Path to valid 5-page PDF"""
    return os.path.join(test_data_dir, "valid_5_pages.pdf")


@pytest.fixture
def valid_pdf_10_pages(test_data_dir):
    """Path to valid 10-page PDF"""
    return os.path.join(test_data_dir, "valid_10_pages.pdf")


@pytest.fixture
def valid_pdf_100_pages(test_data_dir):
    """Path to valid 100-page PDF"""
    return os.path.join(test_data_dir, "valid_100_pages.pdf")


@pytest.fixture
def corrupted_pdf(test_data_dir):
    """Path to corrupted PDF"""
    return os.path.join(test_data_dir, "corrupted.pdf")


@pytest.fixture
def encrypted_pdf(test_data_dir):
    """Path to encrypted PDF"""
    return os.path.join(test_data_dir, "encrypted.pdf")


@pytest.fixture
def fake_pdf(test_data_dir):
    """Path to fake PDF (text file)"""
    return os.path.join(test_data_dir, "fake.pdf")


@pytest.fixture
def empty_pdf(test_data_dir):
    """Path to empty file"""
    return os.path.join(test_data_dir, "empty.pdf")


@pytest.fixture
def medium_pdf(test_data_dir):
    """Path to medium-sized PDF (~5MB)"""
    return os.path.join(test_data_dir, "medium_valid.pdf")


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment before each test"""
    # Ensure test directories exist
    from utils.helpers import ensure_directories_exist
    ensure_directories_exist()
    
    yield
    
    # Cleanup after test (optional)
    # Can add cleanup logic here if needed
