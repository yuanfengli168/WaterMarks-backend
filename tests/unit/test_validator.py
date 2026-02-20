"""
Unit tests for validator module
"""
import pytest
import os
import tempfile
from modules.validator import (
    check_size_allowance,
    validate_file_size_on_upload,
    validate_pdf_structure,
    format_bytes,
    ValidationResult
)


class TestSizeCheck:
    """Tests for size checking functionality"""
    
    def test_small_file_allowed(self):
        """Test that small files are allowed"""
        result = check_size_allowance(1024 * 1024)  # 1MB
        assert result['allowed'] is True
        assert 'acceptable' in result['message'].lower()
    
    def test_zero_size_rejected(self):
        """Test that zero-size files are rejected"""
        result = check_size_allowance(0)
        assert result['allowed'] is False
        assert 'invalid' in result['message'].lower()
    
    def test_negative_size_rejected(self):
        """Test that negative sizes are rejected"""
        result = check_size_allowance(-1000)
        assert result['allowed'] is False
        assert 'invalid' in result['message'].lower()
    
    def test_very_large_file_rejected(self):
        """Test that extremely large files are rejected"""
        result = check_size_allowance(10 * 1024 * 1024 * 1024)  # 10GB
        assert result['allowed'] is False
        assert 'too large' in result['message'].lower()
    
    def test_result_contains_limits(self):
        """Test that result contains required fields"""
        result = check_size_allowance(1024)
        assert 'allowed' in result
        assert 'max_allowed_size' in result
        assert 'available_ram' in result
        assert 'message' in result
        assert result['max_allowed_size'] > 0
        assert result['available_ram'] > 0


class TestFileValidation:
    """Tests for file validation functionality"""
    
    def test_validate_nonexistent_file(self):
        """Test validation of non-existent file"""
        result = validate_pdf_structure("/nonexistent/file.pdf")
        assert result.is_valid is False
        assert 'not found' in result.message.lower()
    
    def test_validate_valid_pdf(self, valid_pdf_1_page):
        """Test validation of valid PDF"""
        result = validate_pdf_structure(valid_pdf_1_page)
        assert result.is_valid is True
        assert result.data['num_pages'] == 1
    
    def test_validate_multi_page_pdf(self, valid_pdf_10_pages):
        """Test validation of multi-page PDF"""
        result = validate_pdf_structure(valid_pdf_10_pages)
        assert result.is_valid is True
        assert result.data['num_pages'] == 10
    
    def test_validate_corrupted_pdf(self, corrupted_pdf):
        """Test validation of corrupted PDF"""
        result = validate_pdf_structure(corrupted_pdf)
        assert result.is_valid is False
        assert any(word in result.message.lower() for word in ['corrupt', 'invalid', 'error'])
    
    def test_validate_encrypted_pdf(self, encrypted_pdf):
        """Test validation of encrypted PDF"""
        result = validate_pdf_structure(encrypted_pdf)
        assert result.is_valid is False
        assert 'password' in result.message.lower() or 'encrypted' in result.message.lower()
    
    def test_validate_fake_pdf(self, fake_pdf):
        """Test validation of fake PDF (text file)"""
        result = validate_pdf_structure(fake_pdf)
        assert result.is_valid is False
    
    def test_validate_empty_file(self, empty_pdf):
        """Test validation of empty file"""
        result = validate_pdf_structure(empty_pdf)
        assert result.is_valid is False
        assert 'empty' in result.message.lower()


class TestFormatBytes:
    """Tests for format_bytes utility"""
    
    def test_format_bytes(self):
        """Test byte formatting"""
        assert "1.0 KB" in format_bytes(1024)
        assert "1.0 MB" in format_bytes(1024 * 1024)
        assert "1.0 GB" in format_bytes(1024 * 1024 * 1024)
    
    def test_format_zero_bytes(self):
        """Test formatting zero bytes"""
        result = format_bytes(0)
        assert "0.0" in result
    
    def test_format_fractional_mb(self):
        """Test formatting fractional MB"""
        result = format_bytes(int(1.5 * 1024 * 1024))
        assert "1.5 MB" in result or "1.4 MB" in result  # Allow for rounding


class TestValidationResult:
    """Tests for ValidationResult class"""
    
    def test_create_valid_result(self):
        """Test creating valid result"""
        result = ValidationResult(True, "Success", {"pages": 10})
        assert result.is_valid is True
        assert result.message == "Success"
        assert result.data["pages"] == 10
    
    def test_create_invalid_result(self):
        """Test creating invalid result"""
        result = ValidationResult(False, "Error occurred")
        assert result.is_valid is False
        assert result.message == "Error occurred"
        assert result.data == {}
