"""
Unit tests for status manager module
"""
import pytest
import time
from datetime import datetime, timedelta
from modules.status_manager import StatusManager, JobStatus


class TestJobStatus:
    """Tests for JobStatus dataclass"""
    
    def test_create_job_status(self):
        """Test creating job status"""
        status = JobStatus(
            job_id="test-123",
            status="uploading",
            progress=10,
            message="Test message"
        )
        
        assert status.job_id == "test-123"
        assert status.status == "uploading"
        assert status.progress == 10
        assert status.message == "Test message"
        assert status.created_at is not None
        assert status.updated_at is not None
    
    def test_job_status_to_dict(self):
        """Test converting job status to dictionary"""
        status = JobStatus(
            job_id="test-123",
            status="finished",
            progress=100,
            message="Complete"
        )
        
        data = status.to_dict()
        
        assert isinstance(data, dict)
        assert data['job_id'] == "test-123"
        assert data['status'] == "finished"
        assert data['progress'] == 100
        assert 'created_at' in data
        assert 'updated_at' in data


class TestStatusManager:
    """Tests for StatusManager"""
    
    @pytest.fixture
    def manager(self):
        """Create fresh StatusManager for each test"""
        return StatusManager()
    
    def test_create_job(self, manager):
        """Test creating a new job"""
        status = manager.create_job("job-1", "Initial message")
        
        assert status.job_id == "job-1"
        assert status.status == "uploading"
        assert status.progress == 0
        assert status.message == "Initial message"
    
    def test_job_exists(self, manager):
        """Test checking if job exists"""
        manager.create_job("job-1")
        
        assert manager.job_exists("job-1") is True
        assert manager.job_exists("nonexistent") is False
    
    def test_get_status(self, manager):
        """Test getting job status"""
        manager.create_job("job-1", "Test")
        
        status = manager.get_status("job-1")
        assert status is not None
        assert status.job_id == "job-1"
        
        # Non-existent job
        status = manager.get_status("nonexistent")
        assert status is None
    
    def test_update_status(self, manager):
        """Test updating job status"""
        manager.create_job("job-1")
        
        updated = manager.update_status(
            "job-1",
            status="splitting",
            message="Splitting PDF"
        )
        
        assert updated is not None
        assert updated.status == "splitting"
        assert updated.message == "Splitting PDF"
        assert updated.progress == 30  # Auto-set based on status
    
    def test_update_nonexistent_job(self, manager):
        """Test updating non-existent job returns None"""
        result = manager.update_status("nonexistent", status="finished")
        assert result is None
    
    def test_auto_progress_by_status(self, manager):
        """Test that progress is auto-set based on status"""
        manager.create_job("job-1")
        
        manager.update_status("job-1", status="uploading")
        assert manager.get_status("job-1").progress == 10
        
        manager.update_status("job-1", status="splitting")
        assert manager.get_status("job-1").progress == 30
        
        manager.update_status("job-1", status="adding_watermarks")
        assert manager.get_status("job-1").progress == 50
        
        manager.update_status("job-1", status="finished")
        assert manager.get_status("job-1").progress == 100
    
    def test_error_status(self, manager):
        """Test setting error status"""
        manager.create_job("job-1")
        
        manager.update_status("job-1", error="Something went wrong")
        
        status = manager.get_status("job-1")
        assert status.status == "error"
        assert status.error == "Something went wrong"
        assert status.progress == 0
    
    def test_delete_job(self, manager):
        """Test deleting a job"""
        manager.create_job("job-1")
        assert manager.job_exists("job-1")
        
        result = manager.delete_job("job-1")
        assert result is True
        assert not manager.job_exists("job-1")
        
        # Deleting non-existent job
        result = manager.delete_job("nonexistent")
        assert result is False
    
    def test_count_active_jobs(self, manager):
        """Test counting active jobs"""
        manager.create_job("job-1")
        manager.create_job("job-2")
        manager.create_job("job-3")
        
        manager.update_status("job-1", status="splitting")
        manager.update_status("job-2", status="adding_watermarks")
        manager.update_status("job-3", status="finished")
        
        # Only job-1 and job-2 are active
        assert manager.count_active_jobs() == 2
    
    def test_get_all_jobs(self, manager):
        """Test getting all jobs"""
        manager.create_job("job-1")
        manager.create_job("job-2")
        
        all_jobs = manager.get_all_jobs()
        assert len(all_jobs) == 2
        assert "job-1" in all_jobs
        assert "job-2" in all_jobs
    
    def test_cleanup_old_jobs(self, manager):
        """Test cleaning up old jobs"""
        # Create a job
        manager.create_job("job-1")
        
        # Manually set created_at to old time
        job = manager._statuses["job-1"]
        job.created_at = datetime.now() - timedelta(hours=5)
        
        # Cleanup jobs older than 1 hour
        count = manager.cleanup_old_jobs(max_age_hours=1)
        
        assert count == 1
        assert not manager.job_exists("job-1")
    
    def test_thread_safety(self, manager):
        """Test thread-safe operations"""
        import threading
        
        def create_jobs():
            for i in range(10):
                manager.create_job(f"job-{threading.get_ident()}-{i}")
        
        threads = [threading.Thread(target=create_jobs) for _ in range(5)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have 50 jobs (5 threads * 10 jobs each)
        assert len(manager.get_all_jobs()) == 50
