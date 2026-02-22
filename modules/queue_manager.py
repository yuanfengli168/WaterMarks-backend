"""
Job Queue Manager - Handles job queuing with JSON persistence
"""
import json
import os
import shutil
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import psutil
import config

# Global variables for container memory tracking
_CONTAINER_LIMIT = None
_BASELINE_USAGE = None
_LIMIT_DETECTED = False


def detect_container_memory_limit() -> int:
    """
    Detect actual container memory limit from cgroup (Linux containers).
    
    Tries cgroup v2 first, then v1, then falls back to env var.
    
    Returns:
        Container memory limit in bytes, or 0 if not in container
    """
    # Try cgroup v2 (newer Docker, Kubernetes)
    try:
        with open('/sys/fs/cgroup/memory.max', 'r') as f:
            value = f.read().strip()
            if value != 'max':
                limit = int(value)
                print(f"🐳 [MEMORY] Detected cgroup v2 limit: {limit / (1024*1024):.0f}MB")
                return limit
    except (FileNotFoundError, PermissionError, ValueError):
        pass
    
    # Try cgroup v1 (older Docker)
    try:
        with open('/sys/fs/cgroup/memory/memory.limit_in_bytes', 'r') as f:
            limit = int(f.read().strip())
            # Filter out unrealistic values (some systems return huge numbers)
            if limit < (1024 ** 4):  # Less than 1TB = probably real
                print(f"🐳 [MEMORY] Detected cgroup v1 limit: {limit / (1024*1024):.0f}MB")
                return limit
    except (FileNotFoundError, PermissionError, ValueError):
        pass
    
    # Fall back to environment variable
    if config.CONTAINER_RAM_LIMIT > 0:
        print(f"🐳 [MEMORY] Using env var limit: {config.CONTAINER_RAM_LIMIT / (1024*1024):.0f}MB")
        return config.CONTAINER_RAM_LIMIT
    
    print("💻 [MEMORY] No container limit detected (running on host)")
    return 0


def get_baseline_memory_usage() -> int:
    """
    Get current process memory usage as baseline.
    
    Returns:
        RSS (Resident Set Size) in bytes
    """
    rss = psutil.Process().memory_info().rss
    print(f"📊 [MEMORY] Baseline process usage: {rss / (1024*1024):.1f}MB")
    return rss


def initialize_memory_tracking():
    """
    Initialize memory tracking on first call.
    Detects container limit and measures baseline usage.
    """
    global _CONTAINER_LIMIT, _BASELINE_USAGE, _LIMIT_DETECTED
    
    if _LIMIT_DETECTED:
        return
    
    _LIMIT_DETECTED = True
    _CONTAINER_LIMIT = detect_container_memory_limit()
    _BASELINE_USAGE = get_baseline_memory_usage()
    
    if _CONTAINER_LIMIT > 0:
        available = _CONTAINER_LIMIT - _BASELINE_USAGE
        print(f"✅ [MEMORY] Available for jobs: {available / (1024*1024):.0f}MB (limit: {_CONTAINER_LIMIT / (1024*1024):.0f}MB - baseline: {_BASELINE_USAGE / (1024*1024):.1f}MB)")
    else:
        print(f"✅ [MEMORY] Running on host, using psutil for memory checks")


def get_effective_available_ram() -> int:
    """
    Get effective available RAM considering container limits and baseline usage.
    
    On containerized environments (Docker, Render), psutil reports the host's RAM,
    not the container's limit. This function:
    1. Detects container limit from cgroup or env var
    2. Subtracts baseline process usage
    3. Returns realistic available RAM for jobs
    
    Returns:
        Effective available RAM in bytes
    """
    initialize_memory_tracking()
    
    memory = psutil.virtual_memory()
    
    # If in container, calculate based on container limit
    if _CONTAINER_LIMIT and _CONTAINER_LIMIT > 0:
        # Current process usage
        current_usage = psutil.Process().memory_info().rss
        # Available = limit - current usage
        container_available = _CONTAINER_LIMIT - current_usage
        # Cap at 0 (can't be negative)
        return max(0, container_available)
    
    # Not in container, use psutil's value (running on host/local)
    return memory.available


class JobQueueManager:
    """
    Manages job queue with JSON file persistence.
    Survives server restarts and handles concurrent access.
    """
    
    def __init__(self, queue_file="queue.json"):
        self.queue_file = queue_file
        self.jobs: Dict[str, dict] = {}
        self.lock = threading.RLock()  # Use RLock for reentrant locking (prevents deadlock)
        self._load_from_disk()
        self._start_cleanup_thread()
    
    def _load_from_disk(self):
        """Load queue state from disk on startup"""
        try:
            if os.path.exists(self.queue_file):
                with open(self.queue_file, 'r') as f:
                    self.jobs = json.load(f)
                print(f"✅ Loaded {len(self.jobs)} jobs from queue file")
            else:
                self.jobs = {}
                print("✅ Starting with empty queue")
        except Exception as e:
            print(f"⚠️ Error loading queue file: {e}. Starting fresh.")
            self.jobs = {}
    
    def _save_to_disk(self):
        """Persist queue state to disk"""
        try:
            with open(self.queue_file, 'w') as f:
                json.dump(self.jobs, f, indent=2, default=str)
        except Exception as e:
            print(f"❌ Error saving queue: {e}")
    
    def _start_cleanup_thread(self):
        """Start background thread for cleanup"""
        def cleanup_loop():
            while True:
                try:
                    self.cleanup_expired_jobs()
                    time.sleep(30)  # Check every 30 seconds
                except Exception as e:
                    print(f"Cleanup error: {e}")
        
        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()
    
    def check_disk_space(self, required_bytes: int) -> Tuple[bool, str]:
        """
        Check if sufficient disk space is available.
        
        Args:
            required_bytes: Bytes needed for this job
            
        Returns:
            (has_space, message)
        """
        try:
            disk = shutil.disk_usage(config.TEMP_DIR)
            
            # Need space for: upload + processed output + safety buffer
            required = required_bytes * 2 + (150 * 1024 * 1024)  # 2x file + 150MB buffer
            
            if disk.free < required:
                available_mb = disk.free / (1024 * 1024)
                required_mb = required / (1024 * 1024)
                return False, f"Insufficient disk space. Available: {available_mb:.0f}MB, Required: {required_mb:.0f}MB"
            
            return True, "OK"
        except Exception as e:
            return False, f"Error checking disk space: {str(e)}"
    
    def can_accept_job(self, session_id: str, file_size: int) -> Tuple[bool, str, Optional[dict]]:
        """
        Check if job can be accepted.
        
        Args:
            session_id: User session identifier
            file_size: Size of file in bytes
            
        Returns:
            (can_accept, message, retry_info)
        """
        with self.lock:
            # REMOVED: One job per user restriction
            # Users can now upload multiple files concurrently
            
            # Check disk space (dynamic limit)
            has_space, space_msg = self.check_disk_space(file_size)
            if not has_space:
                # Estimate when space might be available
                retry_seconds = self.estimate_space_available_time()
                return False, space_msg, {
                    "retry_after_seconds": retry_seconds,
                    "reason": "disk_space"
                }
            
            # Check memory (using container-aware RAM detection)
            available_ram = get_effective_available_ram()
            if available_ram < config.MIN_FREE_RAM_REQUIRED:
                retry_seconds = self.estimate_memory_available_time()
                return False, "Server memory insufficient. Please try again shortly.", {
                    "retry_after_seconds": retry_seconds,
                    "reason": "memory"
                }
            
            return True, "OK", None
    
    def add_job(self, job_id: str, session_id: str, file_path: str, file_size: int, chunk_size: int):
        """
        Add job to queue.
        
        Args:
            job_id: Job identifier
            session_id: User session
            file_path: Path to uploaded file
            file_size: File size in bytes
            chunk_size: Pages per chunk
        """
        with self.lock:
            queue_count = self.get_queue_count()
            
            self.jobs[job_id] = {
                "job_id": job_id,
                "session_id": session_id,
                "file_path": file_path,
                "file_size": file_size,
                "chunk_size": chunk_size,
                "status": "queued",
                "queue_position": queue_count + 1,
                "queued_at": datetime.now().isoformat(),
                "started_at": None,
                "finished_at": None,
                "download_window_expires": None
            }
            
            self._save_to_disk()
    
    def get_job(self, job_id: str) -> Optional[dict]:
        """Get job by ID"""
        with self.lock:
            return self.jobs.get(job_id)
    
    def get_user_job(self, session_id: str) -> Optional[dict]:
        """Get active job for a session"""
        with self.lock:
            for job in self.jobs.values():
                if job.get('session_id') == session_id:
                    status = job.get('status')
                    if status in ['queued', 'processing', 'finished']:
                        return job
            return None
    
    def get_queue_count(self) -> int:
        """Get number of queued jobs"""
        return sum(1 for j in self.jobs.values() if j.get('status') == 'queued')
    
    def get_processing_count(self) -> int:
        """Get number of jobs being processed"""
        return sum(1 for j in self.jobs.values() if j.get('status') == 'processing')
    
    def get_queue_position(self, job_id: str) -> int:
        """Get position in queue (1-indexed)"""
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or job.get('status') != 'queued':
                return 0
            
            # Find all queued jobs and sort by queued_at
            queued_jobs = [
                j for j in self.jobs.values() 
                if j.get('status') == 'queued'
            ]
            queued_jobs.sort(key=lambda x: x.get('queued_at', ''))
            
            for i, j in enumerate(queued_jobs):
                if j['job_id'] == job_id:
                    return i + 1
            
            return 0
    
    def estimate_wait_time(self, job_id: str) -> int:
        """
        Estimate seconds until this job starts processing.
        
        Args:
            job_id: Job to estimate for
            
        Returns:
            Estimated seconds
        """
        position = self.get_queue_position(job_id)
        if position == 0:
            return 0
        
        # Estimate average processing time
        avg_time = self.get_average_processing_time()
        if avg_time is None:
            avg_time = 120  # Default 2 minutes
        
        # Jobs ahead × average time
        return (position) * avg_time
    
    def get_average_processing_time(self) -> Optional[int]:
        """Calculate average processing time from recent completed jobs"""
        with self.lock:
            completed = [
                j for j in self.jobs.values()
                if j.get('status') in ['finished', 'downloaded'] 
                and j.get('started_at') 
                and j.get('finished_at')
            ]
            
            if not completed:
                return None
            
            total_time = 0
            for job in completed[-10:]:  # Last 10 jobs
                try:
                    started = datetime.fromisoformat(job['started_at'])
                    finished = datetime.fromisoformat(job['finished_at'])
                    total_time += (finished - started).total_seconds()
                except:
                    pass
            
            return int(total_time / len(completed)) if completed else None
    
    def estimate_space_available_time(self) -> int:
        """Estimate when disk space will be available"""
        # Look at jobs that will finish soon
        processing = self.get_processing_count()
        if processing > 0:
            avg_time = self.get_average_processing_time() or 120
            return avg_time  # When current job finishes
        return 300  # Default 5 minutes
    
    def estimate_memory_available_time(self) -> int:
        """Estimate when memory will be available"""
        processing = self.get_processing_count()
        if processing > 0:
            avg_time = self.get_average_processing_time() or 120
            return avg_time
        return 60  # Default 1 minute
    
    def get_active_resource_usage(self) -> dict:
        """
        Calculate total RAM and disk usage by active jobs.
        Active jobs include: processing, splitting, adding_watermarks, merging.
        
        Returns:
            dict with ram_used, disk_used, active_count
        """
        with self.lock:
            active_statuses = ['processing', 'splitting', 'adding_watermarks', 'merging']
            active_jobs = [
                j for j in self.jobs.values()
                if j.get('status') in active_statuses
            ]
            
            # Estimate resources used by active jobs
            total_ram = sum(
                int(j.get('file_size', 0) * config.RAM_USAGE_MULTIPLIER)
                for j in active_jobs
            )
            total_disk = sum(
                int(j.get('file_size', 0) * config.DISK_USAGE_MULTIPLIER)
                for j in active_jobs
            )
            
            return {
                'ram_used': total_ram,
                'disk_used': total_disk,
                'active_count': len(active_jobs)
            }
    
    def pop_next_job(self) -> Optional[dict]:
        """
        Get next job from queue if resources available (supports concurrent processing).
        Uses 4x RAM and 2x disk multipliers to estimate resource needs.
        
        Returns:
            Job dict or None if no job ready or insufficient resources
        """
        with self.lock:
            # Get current resource usage by active jobs
            usage = self.get_active_resource_usage()
            
            # Check available resources (container-aware RAM)
            available_ram = get_effective_available_ram()
            disk = shutil.disk_usage(config.TEMP_DIR)
            
            # Get oldest queued job
            queued_jobs = [
                j for j in self.jobs.values()
                if j.get('status') == 'queued'
            ]
            
            if not queued_jobs:
                return None
            
            queued_jobs.sort(key=lambda x: x.get('queued_at', ''))
            next_job = queued_jobs[0]
            
            # Estimate resources needed for this job
            estimated_ram = int(next_job['file_size'] * config.RAM_USAGE_MULTIPLIER)
            estimated_disk = int(next_job['file_size'] * config.DISK_USAGE_MULTIPLIER)
            
            # Check if we can start this job without exceeding buffers
            ram_after = available_ram - estimated_ram
            disk_after = disk.free - estimated_disk
            
            # Must maintain minimum buffers
            if ram_after < config.MIN_RAM_BUFFER:
                print(f"⏸️  [QUEUE] Cannot start job {next_job['job_id']}: would leave only {ram_after / (1024*1024):.1f}MB RAM (need {config.MIN_RAM_BUFFER / (1024*1024):.0f}MB buffer)")
                return None
            
            if disk_after < config.MIN_DISK_BUFFER:
                print(f"⏸️  [QUEUE] Cannot start job {next_job['job_id']}: would leave only {disk_after / (1024*1024):.1f}MB disk (need {config.MIN_DISK_BUFFER / (1024*1024):.0f}MB buffer)")
                return None
            
            # Safe to start this job!
            print(f"🚀 [QUEUE] Starting job {next_job['job_id']} (estimated: {estimated_ram / (1024*1024):.1f}MB RAM, {estimated_disk / (1024*1024):.1f}MB disk)")
            print(f"📊 [QUEUE] Active jobs: {usage['active_count']}, RAM after: {ram_after / (1024*1024):.1f}MB, Disk after: {disk_after / (1024*1024):.1f}MB")
            
            # Mark as processing
            next_job['status'] = 'processing'
            next_job['started_at'] = datetime.now().isoformat()
            self._save_to_disk()
            
            return next_job
    
    def mark_finished(self, job_id: str):
        """Mark job as finished and start download window"""
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id]['status'] = 'finished'
                self.jobs[job_id]['finished_at'] = datetime.now().isoformat()
                # Start 1-minute download window
                expires = datetime.now() + timedelta(minutes=1)
                self.jobs[job_id]['download_window_expires'] = expires.isoformat()
                self._save_to_disk()
    
    def mark_error(self, job_id: str, error: str):
        """Mark job as failed"""
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id]['status'] = 'error'
                self.jobs[job_id]['error'] = error
                self.jobs[job_id]['finished_at'] = datetime.now().isoformat()
                self._save_to_disk()
    
    def mark_downloaded(self, job_id: str):
        """Mark job as downloaded (for cleanup)"""
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id]['status'] = 'downloaded'
                self.jobs[job_id]['downloaded_at'] = datetime.now().isoformat()
                self._save_to_disk()
    
    def cleanup_expired_jobs(self):
        """Remove jobs past their download window"""
        with self.lock:
            now = datetime.now()
            to_delete = []
            
            for job_id, job in self.jobs.items():
                # Delete if download window expired
                if job.get('download_window_expires'):
                    try:
                        expires = datetime.fromisoformat(job['download_window_expires'])
                        if now > expires:
                            to_delete.append(job_id)
                    except:
                        pass
                
                # Delete if downloaded
                if job.get('status') == 'downloaded':
                    to_delete.append(job_id)
                
                # Delete old errors (after 1 hour)
                if job.get('status') == 'error':
                    try:
                        finished = datetime.fromisoformat(job.get('finished_at', ''))
                        if now > finished + timedelta(hours=1):
                            to_delete.append(job_id)
                    except:
                        pass
            
            if to_delete:
                for job_id in to_delete:
                    # Clean up files
                    job = self.jobs[job_id]
                    self._cleanup_job_files(job)
                    del self.jobs[job_id]
                
                self._save_to_disk()
                print(f"🧹 Cleaned up {len(to_delete)} expired jobs")
    
    def _cleanup_job_files(self, job: dict):
        """Delete files for a job"""
        try:
            file_path = job.get('file_path')
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
            
            # Clean up temp processing files
            job_id = job['job_id']
            from utils.helpers import cleanup_job_files
            cleanup_job_files(job_id)
        except Exception as e:
            print(f"Error cleaning up job files: {e}")
    
    def delete_job(self, job_id: str):
        """Manually delete a job"""
        with self.lock:
            if job_id in self.jobs:
                job = self.jobs[job_id]
                self._cleanup_job_files(job)
                del self.jobs[job_id]
                self._save_to_disk()


# Global singleton
_queue_manager = None


def get_queue_manager() -> JobQueueManager:
    """Get global queue manager instance"""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = JobQueueManager()
    return _queue_manager
