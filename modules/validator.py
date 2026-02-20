"""
Validator Module - Handles file size checking and PDF validation
"""
import os
from typing import Dict, Tuple
import psutil
from PyPDF2 import PdfReader
import config


class ValidationResult:
    """Result of a validation check"""
    def __init__(self, is_valid: bool, message: str, data: Dict = None):
        self.is_valid = is_valid
        self.message = message
        self.data = data or {}


def check_size_allowance(file_size: int) -> Dict:
    """
    Check if file size is acceptable before upload.
    
    Args:
        file_size: File size in bytes
        
    Returns:
        Dictionary with allowed status, limits, and message
    """
    try:
        # Get available RAM
        memory = psutil.virtual_memory()
        available_ram = memory.available
        
        # Calculate maximum allowed size
        max_allowed_size = int(available_ram * config.RAM_SAFETY_MARGIN)
        
        # Also enforce absolute maximum
        if max_allowed_size > config.ABSOLUTE_MAX_FILE_SIZE:
            max_allowed_size = config.ABSOLUTE_MAX_FILE_SIZE
        
        # Check if we have minimum free RAM
        if available_ram < config.MIN_FREE_RAM_REQUIRED:
            return {
                "allowed": False,
                "max_allowed_size": max_allowed_size,
                "available_ram": available_ram,
                "message": "Server memory is currently insufficient. Please try again later."
            }
        
        # Check file size
        if file_size <= 0:
            return {
                "allowed": False,
                "max_allowed_size": max_allowed_size,
                "available_ram": available_ram,
                "message": "Invalid file size. File size must be greater than 0."
            }
        
        if file_size > max_allowed_size:
            return {
                "allowed": False,
                "max_allowed_size": max_allowed_size,
                "available_ram": available_ram,
                "message": f"File too large ({format_bytes(file_size)}). Maximum allowed: {format_bytes(max_allowed_size)}"
            }
        
        return {
            "allowed": True,
            "max_allowed_size": max_allowed_size,
            "available_ram": available_ram,
            "message": "File size is acceptable"
        }
        
    except Exception as e:
        return {
            "allowed": False,
            "max_allowed_size": 0,
            "available_ram": 0,
            "message": f"Error checking file size: {str(e)}"
        }


def validate_file_size_on_upload(file_size: int) -> ValidationResult:
    """
    Lightweight re-check of file size during upload.
    Defense against direct API calls bypassing pre-check.
    
    Args:
        file_size: File size in bytes
        
    Returns:
        ValidationResult object
    """
    if not config.RECHECK_SIZE_ON_UPLOAD:
        return ValidationResult(True, "Size check skipped (disabled in config)")
    
    try:
        memory = psutil.virtual_memory()
        available_ram = memory.available
        max_allowed_size = int(available_ram * config.RAM_SAFETY_MARGIN)
        
        # Enforce absolute maximum
        if max_allowed_size > config.ABSOLUTE_MAX_FILE_SIZE:
            max_allowed_size = config.ABSOLUTE_MAX_FILE_SIZE
        
        if file_size > max_allowed_size:
            return ValidationResult(
                False,
                f"File size ({format_bytes(file_size)}) exceeds server capacity ({format_bytes(max_allowed_size)})"
            )
        
        return ValidationResult(True, "File size acceptable")
        
    except Exception as e:
        return ValidationResult(False, f"Error validating file size: {str(e)}")


def validate_pdf_structure(file_path: str) -> ValidationResult:
    """
    Validate PDF file structure and integrity.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        ValidationResult object
    """
    try:
        # Check file exists
        if not os.path.exists(file_path):
            return ValidationResult(False, "File not found")
        
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return ValidationResult(False, "The uploaded file is empty")
        
        # Check file extension
        if not file_path.lower().endswith('.pdf'):
            return ValidationResult(False, "File must be a PDF")
        
        # Try to open and read PDF
        try:
            reader = PdfReader(file_path)
            
            # Check if PDF has pages
            num_pages = len(reader.pages)
            if num_pages == 0:
                return ValidationResult(False, "The PDF file contains no pages")
            
            # Check if PDF is encrypted
            if reader.is_encrypted:
                return ValidationResult(
                    False, 
                    "The PDF is password-protected. Please upload an unencrypted file."
                )
            
            # Try to access first page to ensure it's readable
            try:
                _ = reader.pages[0]
            except Exception as e:
                return ValidationResult(
                    False,
                    "The PDF file appears to be corrupted or damaged"
                )
            
            return ValidationResult(
                True,
                "PDF is valid",
                data={"num_pages": num_pages, "file_size": file_size}
            )
            
        except Exception as e:
            error_msg = str(e).lower()
            
            if "encrypted" in error_msg or "password" in error_msg or "decrypt" in error_msg:
                return ValidationResult(
                    False,
                    "The PDF is password-protected. Please upload an unencrypted file."
                )
            elif "eof" in error_msg or "truncated" in error_msg:
                return ValidationResult(
                    False,
                    "The PDF file is incomplete or corrupted"
                )
            elif "invalid" in error_msg or "malformed" in error_msg:
                return ValidationResult(
                    False,
                    "The uploaded file is not a valid PDF or contains structural errors"
                )
            else:
                return ValidationResult(
                    False,
                    f"Unable to process PDF: {str(e)}"
                )
    
    except Exception as e:
        return ValidationResult(False, f"Error validating PDF: {str(e)}")


def format_bytes(size: int) -> str:
    """
    Format bytes into human-readable string.
    
    Args:
        size: Size in bytes
        
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"
