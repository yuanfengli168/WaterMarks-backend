"""
Status Manager Module - Handles job status tracking and management
"""
import threading
from typing import Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import config


@dataclass
class JobStatus:
    """Status information for a processing job"""
    job_id: str
    status: str  # uploading, splitting, adding_watermarks, finished, error
    progress: int  # 0-100
    message: str
    result_path: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        data = asdict(self)
        # Convert datetime to ISO format strings
        data['created_at'] = self.created_at.isoformat() if self.created_at else None
        data['updated_at'] = self.updated_at.isoformat() if self.updated_at else None
        return data


class StatusManager:
    """Thread-safe manager for job statuses"""
    
    def __init__(self):
        self._statuses: Dict[str, JobStatus] = {}
        self._lock = threading.Lock()
    
    def create_job(self, job_id: str, initial_message: str = "Job created") -> JobStatus:
        """
        Create a new job with initial status.
        
        Args:
            job_id: Unique job identifier
            initial_message: Initial status message
            
        Returns:
            JobStatus object
        """
        with self._lock:
            status = JobStatus(
                job_id=job_id,
                status="uploading",
                progress=0,
                message=initial_message
            )
            self._statuses[job_id] = status
            return status
    
    def update_status(
        self,
        job_id: str,
        status: str = None,
        progress: int = None,
        message: str = None,
        result_path: str = None,
        error: str = None
    ) -> Optional[JobStatus]:
        """
        Update job status.
        
        Args:
            job_id: Job identifier
            status: New status value
            progress: Progress percentage (0-100)
            message: Status message
            result_path: Path to result file
            error: Error message if any
            
        Returns:
            Updated JobStatus object or None if job not found
        """
        with self._lock:
            if job_id not in self._statuses:
                return None
            
            job = self._statuses[job_id]
            
            if status is not None:
                job.status = status
                
                # Automatically set progress based on status
                if status == "uploading":
                    job.progress = 10
                elif status == "splitting":
                    job.progress = 30
                elif status == "adding_watermarks":
                    job.progress = 50
                elif status == "merging":
                    job.progress = 80
                elif status == "finished":
                    job.progress = 100
                elif status == "error":
                    job.progress = 0
            
            if progress is not None:
                job.progress = max(0, min(100, progress))  # Clamp between 0-100
            
            if message is not None:
                job.message = message
            
            if result_path is not None:
                job.result_path = result_path
            
            if error is not None:
                job.error = error
                job.status = "error"
            
            job.updated_at = datetime.now()
            
            return job
    
    def get_status(self, job_id: str) -> Optional[JobStatus]:
        """
        Get current status of a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            JobStatus object or None if not found
        """
        with self._lock:
            return self._statuses.get(job_id)
    
    def job_exists(self, job_id: str) -> bool:
        """
        Check if a job exists.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if job exists
        """
        with self._lock:
            return job_id in self._statuses
    
    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job from tracking.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if job was deleted, False if not found
        """
        with self._lock:
            if job_id in self._statuses:
                del self._statuses[job_id]
                return True
            return False
    
    def cleanup_old_jobs(self, max_age_hours: int = None) -> int:
        """
        Remove jobs older than specified hours.
        
        Args:
            max_age_hours: Maximum age in hours (defaults to config)
            
        Returns:
            Number of jobs cleaned up
        """
        if max_age_hours is None:
            max_age_hours = config.JOB_RETENTION_HOURS
        
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        with self._lock:
            jobs_to_delete = [
                job_id for job_id, status in self._statuses.items()
                if status.created_at < cutoff_time
            ]
            
            for job_id in jobs_to_delete:
                del self._statuses[job_id]
            
            return len(jobs_to_delete)
    
    def get_all_jobs(self) -> Dict[str, JobStatus]:
        """
        Get all job statuses (for debugging/admin).
        
        Returns:
            Dictionary of all jobs
        """
        with self._lock:
            return self._statuses.copy()
    
    def count_active_jobs(self) -> int:
        """
        Count jobs that are currently processing.
        
        Returns:
            Number of active jobs
        """
        active_statuses = ["uploading", "splitting", "adding_watermarks", "merging"]
        
        with self._lock:
            return sum(
                1 for status in self._statuses.values()
                if status.status in active_statuses
            )


# Global instance
_status_manager = StatusManager()


def get_status_manager() -> StatusManager:
    """Get the global status manager instance"""
    return _status_manager
