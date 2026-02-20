"""
Integration tests for API endpoints
"""
import pytest
import time
import os
from io import BytesIO


class TestHealthEndpoints:
    """Tests for health check endpoints"""
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "WaterMarks Backend"
        assert data["status"] == "online"
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "active_jobs" in data


class TestSizeCheckEndpoint:
    """Tests for size check endpoint"""
    
    def test_check_small_size(self, client):
        """Test checking small file size"""
        response = client.post(
            "/api/check-size",
            json={"file_size": 1024 * 1024}  # 1MB
        )
        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is True
        assert "max_allowed_size" in data
        assert "available_ram" in data
    
    def test_check_large_size(self, client):
        """Test checking very large file size"""
        response = client.post(
            "/api/check-size",
            json={"file_size": 10 * 1024 * 1024 * 1024}  # 10GB
        )
        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is False
        assert "too large" in data["message"].lower()
    
    def test_check_zero_size(self, client):
        """Test checking zero file size"""
        response = client.post(
            "/api/check-size",
            json={"file_size": 0}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is False
    
    def test_check_negative_size(self, client):
        """Test checking negative file size"""
        response = client.post(
            "/api/check-size",
            json={"file_size": -1000}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is False


class TestUploadEndpoint:
    """Tests for upload endpoint"""
    
    def test_upload_valid_pdf(self, client, valid_pdf_1_page):
        """Test uploading valid PDF"""
        with open(valid_pdf_1_page, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"chunk_size": 5}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert "message" in data
        assert len(data["job_id"]) > 0
    
    def test_upload_with_default_chunk_size(self, client, valid_pdf_1_page):
        """Test uploading with default chunk size"""
        with open(valid_pdf_1_page, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.pdf", f, "application/pdf")}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
    
    def test_upload_corrupted_pdf(self, client, corrupted_pdf):
        """Test uploading corrupted PDF"""
        with open(corrupted_pdf, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"chunk_size": 5}
            )
        
        assert response.status_code == 400
        assert "corrupt" in response.json()["detail"].lower() or "invalid" in response.json()["detail"].lower()
    
    def test_upload_encrypted_pdf(self, client, encrypted_pdf):
        """Test uploading encrypted PDF"""
        with open(encrypted_pdf, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"chunk_size": 5}
            )
        
        assert response.status_code == 400
        detail = response.json()["detail"].lower()
        assert "password" in detail or "encrypted" in detail
    
    def test_upload_fake_pdf(self, client, fake_pdf):
        """Test uploading fake PDF (text file)"""
        with open(fake_pdf, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"chunk_size": 5}
            )
        
        assert response.status_code == 400
    
    def test_upload_empty_file(self, client, empty_pdf):
        """Test uploading empty file"""
        with open(empty_pdf, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"chunk_size": 5}
            )
        
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()
    
    def test_upload_with_invalid_chunk_size(self, client, valid_pdf_1_page):
        """Test uploading with invalid chunk size"""
        with open(valid_pdf_1_page, "rb") as f:
            response = client.post(
                "/api/upload",
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"chunk_size": 0}
            )
        
        assert response.status_code == 400
        assert "chunk size" in response.json()["detail"].lower()
    
    def test_upload_non_pdf_file(self, client):
        """Test uploading non-PDF file"""
        file_content = b"This is not a PDF"
        response = client.post(
            "/api/upload",
            files={"file": ("test.txt", BytesIO(file_content), "text/plain")},
            data={"chunk_size": 5}
        )
        
        assert response.status_code == 400
        assert "pdf" in response.json()["detail"].lower()


class TestStatusEndpoint:
    """Tests for status endpoint"""
    
    def test_get_status_for_valid_job(self, client, valid_pdf_1_page):
        """Test getting status for valid job"""
        # Upload file first
        with open(valid_pdf_1_page, "rb") as f:
            upload_response = client.post(
                "/api/upload",
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"chunk_size": 5}
            )
        
        job_id = upload_response.json()["job_id"]
        
        # Get status
        response = client.get(f"/api/status/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert "status" in data
        assert "progress" in data
        assert "message" in data
    
    def test_get_status_for_nonexistent_job(self, client):
        """Test getting status for non-existent job"""
        response = client.get("/api/status/nonexistent-job-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestDownloadEndpoint:
    """Tests for download endpoint"""
    
    def test_download_before_completion(self, client, valid_pdf_1_page):
        """Test downloading before job is complete"""
        # Upload file
        with open(valid_pdf_1_page, "rb") as f:
            upload_response = client.post(
                "/api/upload",
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"chunk_size": 5}
            )
        
        job_id = upload_response.json()["job_id"]
        
        # Try to download immediately (might not be ready)
        response = client.get(f"/api/download/{job_id}")
        
        # Should either get the file or a "not ready" error
        if response.status_code == 400:
            assert "not ready" in response.json()["detail"].lower()
        elif response.status_code == 200:
            assert response.headers["content-type"] == "application/pdf"
    
    def test_download_nonexistent_job(self, client):
        """Test downloading non-existent job"""
        response = client.get("/api/download/nonexistent-job-id")
        assert response.status_code == 404


class TestCleanupEndpoint:
    """Tests for cleanup endpoint"""
    
    def test_cleanup_existing_job(self, client, valid_pdf_1_page):
        """Test cleaning up existing job"""
        # Upload file
        with open(valid_pdf_1_page, "rb") as f:
            upload_response = client.post(
                "/api/upload",
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"chunk_size": 5}
            )
        
        job_id = upload_response.json()["job_id"]
        
        # Wait a moment for job to be created
        time.sleep(0.5)
        
        # Cleanup
        response = client.delete(f"/api/cleanup/{job_id}")
        assert response.status_code == 200
        assert "cleaned up" in response.json()["message"].lower()
    
    def test_cleanup_nonexistent_job(self, client):
        """Test cleaning up non-existent job"""
        response = client.delete("/api/cleanup/nonexistent-job-id")
        assert response.status_code == 404


class TestAdminEndpoints:
    """Tests for admin endpoints"""
    
    def test_list_all_jobs(self, client):
        """Test listing all jobs"""
        response = client.get("/api/admin/jobs")
        assert response.status_code == 200
        data = response.json()
        assert "total_jobs" in data
        assert "active_jobs" in data
        assert "jobs" in data
    
    def test_cleanup_old_jobs(self, client):
        """Test cleanup old jobs endpoint"""
        response = client.post("/api/admin/cleanup-old")
        assert response.status_code == 200
        data = response.json()
        assert "cleaned up" in data["message"].lower()


class TestFullWorkflow:
    """Integration tests for complete workflow"""
    
    def test_complete_workflow_small_pdf(self, client, valid_pdf_1_page):
        """Test complete workflow with small PDF"""
        # 1. Check size
        file_size = os.path.getsize(valid_pdf_1_page)
        size_response = client.post(
            "/api/check-size",
            json={"file_size": file_size}
        )
        assert size_response.json()["allowed"] is True
        
        # 2. Upload
        with open(valid_pdf_1_page, "rb") as f:
            upload_response = client.post(
                "/api/upload",
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"chunk_size": 5}
            )
        assert upload_response.status_code == 200
        job_id = upload_response.json()["job_id"]
        
        # 3. Poll status until finished
        max_attempts = 30
        for _ in range(max_attempts):
            status_response = client.get(f"/api/status/{job_id}")
            status = status_response.json()["status"]
            
            if status == "finished":
                break
            elif status == "error":
                pytest.fail(f"Job failed: {status_response.json()['error']}")
            
            time.sleep(0.5)
        
        # Should be finished
        final_status = client.get(f"/api/status/{job_id}").json()
        assert final_status["status"] == "finished"
        assert final_status["progress"] == 100
        
        # 4. Download
        download_response = client.get(f"/api/download/{job_id}")
        assert download_response.status_code == 200
        assert download_response.headers["content-type"] == "application/pdf"
        assert len(download_response.content) > 0
        
        # 5. Cleanup
        cleanup_response = client.delete(f"/api/cleanup/{job_id}")
        assert cleanup_response.status_code == 200
    
    def test_complete_workflow_multi_page_pdf(self, client, valid_pdf_10_pages):
        """Test complete workflow with multi-page PDF"""
        file_size = os.path.getsize(valid_pdf_10_pages)
        
        # Check size
        size_response = client.post(
            "/api/check-size",
            json={"file_size": file_size}
        )
        assert size_response.json()["allowed"] is True
        
        # Upload with small chunk size to test chunking
        with open(valid_pdf_10_pages, "rb") as f:
            upload_response = client.post(
                "/api/upload",
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"chunk_size": 3}  # Will create 4 chunks
            )
        assert upload_response.status_code == 200
        job_id = upload_response.json()["job_id"]
        
        # Poll status
        max_attempts = 60
        for _ in range(max_attempts):
            status_response = client.get(f"/api/status/{job_id}")
            status_data = status_response.json()
            
            if status_data["status"] == "finished":
                break
            elif status_data["status"] == "error":
                pytest.fail(f"Job failed: {status_data['error']}")
            
            time.sleep(0.5)
        
        # Verify finished
        final_status = client.get(f"/api/status/{job_id}").json()
        assert final_status["status"] == "finished"
        
        # Download and verify
        download_response = client.get(f"/api/download/{job_id}")
        assert download_response.status_code == 200
        
        # Save and verify PDF has correct page count
        import tempfile
        from PyPDF2 import PdfReader
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(download_response.content)
            tmp_path = tmp.name
        
        try:
            reader = PdfReader(tmp_path)
            assert len(reader.pages) == 10  # Should have same page count as original
        finally:
            os.unlink(tmp_path)
