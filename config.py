"""
Configuration settings for WaterMarks Backend
"""
import os
from typing import List

# Server Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# File Size Limits
RAM_SAFETY_MARGIN = float(os.getenv("RAM_SAFETY_MARGIN", "0.7"))  # Use 70% of available RAM as max
ABSOLUTE_MAX_FILE_SIZE = int(os.getenv("ABSOLUTE_MAX_FILE_SIZE", 500 * 1024 * 1024))  # 500MB hard limit
MIN_FREE_RAM_REQUIRED = int(os.getenv("MIN_FREE_RAM_REQUIRED", 100 * 1024 * 1024))  # Keep 100MB free

# Size Re-check on Upload
RECHECK_SIZE_ON_UPLOAD = os.getenv("RECHECK_SIZE_ON_UPLOAD", "True").lower() == "true"

# Processing Configuration
MAX_PARALLEL_WORKERS = int(os.getenv("MAX_PARALLEL_WORKERS", 4))  # Max concurrent watermark operations
DEFAULT_CHUNK_SIZE = int(os.getenv("DEFAULT_CHUNK_SIZE", 10))  # Default pages per chunk

# Watermark Configuration
WATERMARK_TEXT = os.getenv("WATERMARK_TEXT", "WATERMARK")
WATERMARK_FONT_SIZE = int(os.getenv("WATERMARK_FONT_SIZE", 60))
WATERMARK_OPACITY = float(os.getenv("WATERMARK_OPACITY", "0.3"))  # 0.0 to 1.0
WATERMARK_ROTATION = int(os.getenv("WATERMARK_ROTATION", 45))  # Degrees

# Color palette for chunks (will rotate through these)
WATERMARK_COLORS: List[tuple] = [
    (1, 0, 0),      # Red
    (0, 0, 1),      # Blue
    (0, 0.5, 0),    # Green
    (1, 0.5, 0),    # Orange
    (0.5, 0, 0.5),  # Purple
    (0, 0.8, 0.8),  # Cyan
    (1, 0, 1),      # Magenta
    (0.6, 0.4, 0.2) # Brown
]

# File Storage
TEMP_DIR = os.getenv("TEMP_DIR", "temp_files")
UPLOAD_DIR = os.path.join(TEMP_DIR, "uploads")
PROCESSING_DIR = os.path.join(TEMP_DIR, "processing")
OUTPUT_DIR = os.path.join(TEMP_DIR, "outputs")

# Job Management
JOB_RETENTION_HOURS = int(os.getenv("JOB_RETENTION_HOURS", "1"))  # Clean up jobs after 1 hour
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "10"))

# CORS Configuration (for frontend)
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

# Allowed file extensions
ALLOWED_EXTENSIONS = [".pdf"]
