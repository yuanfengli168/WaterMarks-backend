"""
Helper utility functions
"""
import os
import uuid
import shutil
from typing import Optional
import config


def generate_job_id() -> str:
    """
    Generate a unique job ID.
    
    Returns:
        Unique job identifier
    """
    return str(uuid.uuid4())


def ensure_directories_exist():
    """
    Ensure all required directories exist.
    """
    directories = [
        config.TEMP_DIR,
        config.UPLOAD_DIR,
        config.PROCESSING_DIR,
        config.OUTPUT_DIR
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def cleanup_job_files(job_id: str) -> bool:
    """
    Clean up all files associated with a job.
    
    Args:
        job_id: Job identifier
        
    Returns:
        True if cleanup successful
    """
    try:
        # Remove processing directory
        job_dir = os.path.join(config.PROCESSING_DIR, job_id)
        if os.path.exists(job_dir):
            shutil.rmtree(job_dir)
        
        # Remove uploaded file
        upload_path = os.path.join(config.UPLOAD_DIR, f"{job_id}.pdf")
        if os.path.exists(upload_path):
            os.remove(upload_path)
        
        # Remove output file
        output_path = os.path.join(config.OUTPUT_DIR, f"watermarked_{job_id}.pdf")
        if os.path.exists(output_path):
            os.remove(output_path)
        
        return True
    except Exception as e:
        print(f"Error cleaning up job {job_id}: {str(e)}")
        return False


def get_file_extension(filename: str) -> str:
    """
    Get file extension from filename.
    
    Args:
        filename: Name of file
        
    Returns:
        File extension (including dot)
    """
    return os.path.splitext(filename)[1].lower()


def is_allowed_file(filename: str) -> bool:
    """
    Check if file extension is allowed.
    
    Args:
        filename: Name of file
        
    Returns:
        True if file type is allowed
    """
    return get_file_extension(filename) in config.ALLOWED_EXTENSIONS
