"""
WaterMarks Backend - FastAPI Application
Main application file with all API endpoints
"""
import os
import threading
import time
from typing import Optional
from datetime import datetime, timedelta
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, Response, Cookie
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
from modules.queue_manager import get_queue_manager
from modules.session_manager import get_or_create_session
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

# Get manager instances
status_manager = get_status_manager()
queue_manager = get_queue_manager()


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
    queue_position: Optional[int] = None
    jobs_ahead: Optional[int] = None
    estimated_wait_seconds: Optional[int] = None
    estimated_start_time: Optional[str] = None


class ServerBusyResponse(BaseModel):
    error: str
    message: str
    retry_after_seconds: int
    retry_after_time: str
    reason: str


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    ensure_directories_exist()
    
    # Start background queue processor
    def queue_processor():
        print("🚀 [QUEUE] Queue processor thread started")
        while True:
            try:
                # Try to get next job from queue
                next_job = queue_manager.pop_next_job()
                
                if next_job:
                    print(f"📤 [QUEUE] Popped job {next_job['job_id']} from queue")
                    # Process this job
                    process_queued_job(next_job)
                else:
                    # No job ready or not enough memory, wait a bit
                    time.sleep(2)
            except Exception as e:
                print(f"❌ Queue processor error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(5)
    
    thread = threading.Thread(target=queue_processor, daemon=True)
    thread.start()
    
    print("✅ WaterMarks Backend started successfully")
    print(f"📁 Temp directory: {config.TEMP_DIR}")
    print(f"🎨 Watermark colors: {len(config.WATERMARK_COLORS)} colors available")
    print(f"🔄 Queue processor started")


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
    Returns 200 OK if server is healthy + queue status.
    """
    import psutil
    
    try:
        memory = psutil.virtual_memory()
        return {
            "status": "healthy",
            "server": "running",
            "active_jobs": status_manager.count_active_jobs(),
            "queue": {
                "queued_jobs": queue_manager.get_queue_count(),
                "processing_jobs": queue_manager.get_processing_count()
            },
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
    return {"pong": True, "timestamp": time.time()}


def process_queued_job(job: dict):
    """
    Background function to process a job from queue.
    
    Args:
        job: Job dict from queue
    """
    job_id = job['job_id']
    print(f"🔄 [QUEUE] Processing job {job_id}")
    
    try:
        # Update status to processing (job already created in upload endpoint)
        print(f"📝 [STATUS] Updating {job_id} to 'processing'")
        status_manager.update_status(job_id, status="processing", message="Starting processing from queue")
        
        def status_callback(status):
            print(f"📝 [STATUS] Job {job_id} -> {status}")
            status_manager.update_status(job_id, status=status)
        
        # Process PDF
        result_path = process_pdf_with_watermarks(
            input_pdf_path=job['file_path'],
            chunk_size=job['chunk_size'],
            job_id=job_id,
            status_callback=status_callback
        )
        
        # Update final status
        status_manager.update_status(
            job_id,
            status="finished",
            message="PDF processed successfully. Download within 1 minute.",
            result_path=result_path
        )
        
        # Mark as finished in queue (starts 1-minute timer)
        queue_manager.mark_finished(job_id)
        
    except MemoryError as e:
        error_msg = f"Memory exhausted: {str(e)}. Please try a smaller file."
        status_manager.update_status(
            job_id,
            status="error",
            message="Server out of memory",
            error=error_msg
        )
        queue_manager.mark_error(job_id, error_msg)
        cleanup_job_files(job_id)
        
    except Exception as e:
        error_msg = str(e)
        if "memory" in error_msg.lower() or "overflow" in error_msg.lower():
            error_msg = f"Processing failed due to insufficient memory. Error: {error_msg}"
        
        status_manager.update_status(
            job_id,
            status="error",
            message="Processing failed",
            error=error_msg
        )
        queue_manager.mark_error(job_id, error_msg)
        cleanup_job_files(job_id)


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
    response: Response,
    file: UploadFile = File(...),
    chunk_size: int = Form(default=config.DEFAULT_CHUNK_SIZE),
    session_id: Optional[str] = Cookie(default=None)
):
    """
    Upload PDF file for processing.
    Uses queue system with session-based user tracking.
    
    Args:
        file: PDF file to process
        chunk_size: Number of pages per chunk
        session_id: User session (cookie)
        
    Returns:
        UploadResponse with job_id or 503 if server busy
    """
    print(f"📤 [UPLOAD] Received upload request for file: {file.filename}")
    try:
        # Get or create session
        print(f"🔑 [UPLOAD] Getting/creating session for: {session_id}")
        session = get_or_create_session(session_id)
        response.set_cookie(key="session_id", value=session, httponly=True, max_age=86400)
        
        # Validate file type
        print(f"✅ [UPLOAD] Validating file type: {file.filename}")
        if not is_allowed_file(file.filename):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only PDF files are allowed."
            )
        
        # Validate chunk size
        print(f"✅ [UPLOAD] Validating chunk_size: {chunk_size}")
        if chunk_size <= 0:
            raise HTTPException(
                status_code=400,
                detail="Chunk size must be greater than 0"
            )
        
        # Read file
        print(f"📖 [UPLOAD] Reading file content...")
        content = await file.read()
        file_size = len(content)
        print(f"📖 [UPLOAD] File read complete. Size: {file_size} bytes")
        
        # Check if queue can accept this job
        print(f"🔍 [UPLOAD] Checking if queue can accept job (session: {session}, size: {file_size})")
        can_accept, message, retry_info = queue_manager.can_accept_job(session, file_size)
        
        if not can_accept:
            # Server busy - return 503 with retry info
            if retry_info:
                retry_time = datetime.now() + timedelta(seconds=retry_info['retry_after_seconds'])
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "Server at capacity",
                        "message": f"{message} Please try again in {retry_info['retry_after_seconds'] // 60} minutes.",
                        "retry_after_seconds": retry_info['retry_after_seconds'],
                        "retry_after_time": retry_time.isoformat(),
                        "reason": retry_info['reason']
                    }
                )
        
        # Generate job ID
        job_id = generate_job_id()
        
        # Save uploaded file to disk (NOT in memory)
        upload_path = os.path.join(config.UPLOAD_DIR, f"{job_id}.pdf")
        with open(upload_path, "wb") as buffer:
            buffer.write(content)
        
        del content  # Free memory immediately
        
        # Validate PDF structure
        pdf_validation = validate_pdf_structure(upload_path)
        if not pdf_validation.is_valid:
            os.remove(upload_path)  # Clean up
            raise HTTPException(status_code=400, detail=pdf_validation.message)
        
        # Add to queue
        print(f"➕ [QUEUE] Adding job {job_id} to queue")
        queue_manager.add_job(
            job_id=job_id,
            session_id=session,
            file_path=upload_path,
            file_size=file_size,
            chunk_size=chunk_size
        )
        
        # Create status tracking
        print(f"📝 [STATUS] Creating job {job_id} with status 'queued'")
        status_manager.create_job(job_id, "Queued for processing")
        
        return UploadResponse(
            job_id=job_id,
            message="File uploaded successfully. Added to processing queue."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/status/{job_id}", response_model=StatusResponse)
async def get_job_status(job_id: str):
    """
    Get current status of a processing job.
    Shows queue position if queued, processing status if active.
    
    Args:
        job_id: Job identifier
        
    Returns:
        StatusResponse with current job status and queue info
    """
    try:
        # Check queue first
        queue_job = queue_manager.get_job(job_id)
        
        if queue_job:
            if queue_job['status'] == 'queued':
                # Job is waiting in queue
                position = queue_manager.get_queue_position(job_id)
                wait_seconds = queue_manager.estimate_wait_time(job_id)
                start_time = datetime.now() + timedelta(seconds=wait_seconds)
                
                return StatusResponse(
                    job_id=job_id,
                    status="queued",
                    progress=0,
                    message=f"Your job is queued. {position - 1} job(s) ahead of you.",
                    queue_position=position,
                    jobs_ahead=position - 1,
                    estimated_wait_seconds=wait_seconds,
                    estimated_start_time=start_time.isoformat()
                )
            
            elif queue_job['status'] == 'finished':
                # Check if download window expired
                if queue_job.get('download_window_expires'):
                    expires = datetime.fromisoformat(queue_job['download_window_expires'])
                    if datetime.now() > expires:
                        raise HTTPException(
                            status_code=410,
                            detail="Download window expired (1 minute limit). Please resubmit your file."
                        )
        
        # Check processing status
        status = status_manager.get_status(job_id)
        
        if status is None:
            raise HTTPException(status_code=404, detail="Job not found")
        
        response_data = status.to_dict()
        response_data['queue_position'] = 0
        response_data['jobs_ahead'] = 0
        
        return StatusResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")


@app.get("/api/download/{job_id}")
async def download_pdf(job_id: str):
    """
    Download processed PDF file.
    File is deleted immediately after successful response (200 OK).
    1-minute download window from job completion.
    
    Args:
        job_id: Job identifier
        
    Returns:
        FileResponse with processed PDF
    """
    try:
        # Check queue status
        queue_job = queue_manager.get_job(job_id)
        
        if queue_job:
            # Check if download window expired
            if queue_job.get('download_window_expires'):
                expires = datetime.fromisoformat(queue_job['download_window_expires'])
                if datetime.now() > expires:
                    raise HTTPException(
                        status_code=410,
                        detail="Download window expired (1 minute limit). File has been deleted. Please resubmit."
                    )
        
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
            raise HTTPException(status_code=404, detail="Result file not found. May have been deleted.")
        
        # Create response
        response = FileResponse(
            path=status.result_path,
            media_type="application/pdf",
            filename=f"watermarked_{job_id}.pdf"
        )
        
        # Mark as downloaded and schedule immediate cleanup
        # File will be deleted by background cleanup thread
        queue_manager.mark_downloaded(job_id)
        status_manager.delete_job(job_id)
        
        return response
        
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
