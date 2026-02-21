"""
WaterMarks Backend - FastAPI Application
Main application file with all API endpoints
"""
import os
import threading
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import psutil

import config
from modules.validator import (
    check_size_allowance,
    validate_file_size_on_upload,
    validate_pdf_structure
)
from modules.processor import process_pdf_with_watermarks
from modules.status_manager import get_status_manager
from utils.helpers import (
    generate_job_id,
    ensure_directories_exist,
    cleanup_job_files,
    is_allowed_file
)

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="WaterMarks Backend API",
    description="PDF Watermarking Service - Split, watermark, and merge PDFs",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if config.DEBUG else config.CORS_ORIGINS,  # Allow all origins in debug mode
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get status manager instance
status_manager = get_status_manager()


# Pydantic models for request/response
class SizeCheckRequest(BaseModel):
    file_size: int


class SizeCheckResponse(BaseModel):
    allowed: bool
    max_allowed_size: int
    available_ram: int
    message: str


class UploadResponse(BaseModel):
    job_id: str
    message: str


class StatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    message: str
    result_path: Optional[str] = None
    error: Optional[str] = None


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    ensure_directories_exist()
    print("✅ WaterMarks Backend started successfully")
    print(f"📁 Temp directory: {config.TEMP_DIR}")
    print(f"🎨 Watermark colors: {len(config.WATERMARK_COLORS)} colors available")


# Health check endpoint
@app.get("/")
async def root():
    """Root endpoint - health check"""
    return {
        "service": "WaterMarks Backend",
        "status": "online",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring and Render wake-up.
    Returns 200 OK if server is healthy.
    """
    import psutil
    
    try:
        memory = psutil.virtual_memory()
        return {
            "status": "healthy",
            "server": "running",
            "active_jobs": status_manager.count_active_jobs(),
            "memory": {
                "available_mb": round(memory.available / (1024 * 1024), 2),
                "percent_used": memory.percent
            },
            "uptime": "ok"
        }
    except Exception as e:
        return {
            "status": "degraded",
            "server": "running",
            "error": str(e)
        }


@app.get("/ping")
async def ping():
    """Simple ping endpoint for wake-up calls"""
    return {"pong": True, "timestamp": __import__('time').time()}


# API Endpoints
@app.post("/api/check-size", response_model=SizeCheckResponse)
async def check_file_size(request: SizeCheckRequest):
    """
    Pre-upload size check endpoint.
    Frontend calls this before uploading to verify file size is acceptable.
    
    Args:
        request: SizeCheckRequest with file_size in bytes
        
    Returns:
        SizeCheckResponse with allowed status and limits
    """
    try:
        result = check_size_allowance(request.file_size)
        return SizeCheckResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking file size: {str(e)}")


@app.post("/api/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    chunk_size: int = Form(default=config.DEFAULT_CHUNK_SIZE)
):
    """
    Upload PDF file for processing.
    
    Args:
        file: PDF file to process
        chunk_size: Number of pages per chunk
        
    Returns:
        UploadResponse with job_id for tracking
    """
    try:
        # Validate file type
        if not is_allowed_file(file.filename):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only PDF files are allowed."
            )
        
        # Validate chunk size
        if chunk_size <= 0:
            raise HTTPException(
                status_code=400,
                detail="Chunk size must be greater than 0"
            )
        
        # Generate job ID
        job_id = generate_job_id()
        
        # Create job status
        status_manager.create_job(job_id, "Uploading file")
        
        # Save uploaded file
        upload_path = os.path.join(config.UPLOAD_DIR, f"{job_id}.pdf")
        
        with open(upload_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        file_size = len(content)
        
        # Lightweight size re-check
        size_check = validate_file_size_on_upload(file_size)
        if not size_check.is_valid:
            cleanup_job_files(job_id)
            status_manager.delete_job(job_id)
            raise HTTPException(status_code=413, detail=size_check.message)
        
        # Validate PDF structure
        pdf_validation = validate_pdf_structure(upload_path)
        if not pdf_validation.is_valid:
            cleanup_job_files(job_id)
            status_manager.delete_job(job_id)
            raise HTTPException(status_code=400, detail=pdf_validation.message)
        
        # Update status
        status_manager.update_status(
            job_id,
            status="uploading",
            message=f"PDF validated ({pdf_validation.data.get('num_pages')} pages)"
        )
        
        # Start processing in background thread
        def process_in_background():
            try:
                # Check memory before starting
                memory = psutil.virtual_memory()
                available_ram = memory.available
                if available_ram < config.MIN_FREE_RAM_REQUIRED:
                    raise MemoryError(
                        f"Insufficient memory to process file. "
                        f"Available: {available_ram / (1024*1024):.1f}MB, "
                        f"Required: {config.MIN_FREE_RAM_REQUIRED / (1024*1024):.1f}MB"
                    )
                
                def status_callback(status):
                    status_manager.update_status(job_id, status=status)
                
                # Process PDF
                result_path = process_pdf_with_watermarks(
                    input_pdf_path=upload_path,
                    chunk_size=chunk_size,
                    job_id=job_id,
                    status_callback=status_callback
                )
                
                # Update final status
                status_manager.update_status(
                    job_id,
                    status="finished",
                    message="PDF processed successfully",
                    result_path=result_path
                )
                
            except MemoryError as e:
                status_manager.update_status(
                    job_id,
                    status="error",
                    message="Server out of memory",
                    error=f"Memory exhausted: {str(e)}. Please try a smaller file or upgrade server plan."
                )
                cleanup_job_files(job_id)
            except Exception as e:
                error_msg = str(e)
                # Check if it's a memory-related error
                if "memory" in error_msg.lower() or "overflow" in error_msg.lower():
                    error_msg = f"Processing failed due to insufficient memory. File may be too large for server capacity. Error: {error_msg}"
                
                status_manager.update_status(
                    job_id,
                    status="error",
                    message="Processing failed",
                    error=error_msg
                )
                cleanup_job_files(job_id)
        
        # Start background processing
        thread = threading.Thread(target=process_in_background, daemon=True)
        thread.start()
        
        return UploadResponse(
            job_id=job_id,
            message="File uploaded successfully. Processing started."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/status/{job_id}", response_model=StatusResponse)
async def get_job_status(job_id: str):
    """
    Get current status of a processing job.
    
    Args:
        job_id: Job identifier
        
    Returns:
        StatusResponse with current job status
    """
    try:
        status = status_manager.get_status(job_id)
        
        if status is None:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return StatusResponse(**status.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")


@app.get("/api/download/{job_id}")
async def download_pdf(job_id: str):
    """
    Download processed PDF file.
    
    Args:
        job_id: Job identifier
        
    Returns:
        FileResponse with processed PDF
    """
    try:
        # Check job status
        status = status_manager.get_status(job_id)
        
        if status is None:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if status.status != "finished":
            raise HTTPException(
                status_code=400,
                detail=f"Job not ready. Current status: {status.status}"
            )
        
        if not status.result_path or not os.path.exists(status.result_path):
            raise HTTPException(status_code=404, detail="Result file not found")
        
        # Return file
        return FileResponse(
            path=status.result_path,
            media_type="application/pdf",
            filename=f"watermarked_{job_id}.pdf"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@app.delete("/api/cleanup/{job_id}")
async def cleanup_job(job_id: str):
    """
    Clean up job files and remove from tracking.
    
    Args:
        job_id: Job identifier
        
    Returns:
        Success message
    """
    try:
        if not status_manager.job_exists(job_id):
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Clean up files
        cleanup_job_files(job_id)
        
        # Remove from status manager
        status_manager.delete_job(job_id)
        
        return {"message": f"Job {job_id} cleaned up successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


# Admin/Debug endpoints (optional)
@app.get("/api/admin/jobs")
async def list_all_jobs():
    """
    List all jobs (for debugging/admin).
    
    Returns:
        Dictionary of all jobs
    """
    jobs = status_manager.get_all_jobs()
    return {
        "total_jobs": len(jobs),
        "active_jobs": status_manager.count_active_jobs(),
        "jobs": {job_id: status.to_dict() for job_id, status in jobs.items()}
    }


@app.post("/api/admin/cleanup-old")
async def cleanup_old_jobs():
    """
    Clean up jobs older than configured retention time.
    
    Returns:
        Number of jobs cleaned up
    """
    count = status_manager.cleanup_old_jobs()
    return {"message": f"Cleaned up {count} old jobs"}


# Main entry point
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG
    )
