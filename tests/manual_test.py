#!/usr/bin/env python3
"""
Manual Testing Script for WaterMarks Backend
Interactive CLI for testing API endpoints
"""
import requests
import time
import os
import sys
from pathlib import Path


# Configuration
BASE_URL = os.getenv("API_URL", "http://localhost:8000")
TEST_DATA_DIR = "tests/test_data"


def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_success(text):
    """Print success message"""
    print(f"✅ {text}")


def print_error(text):
    """Print error message"""
    print(f"❌ {text}")


def print_info(text):
    """Print info message"""
    print(f"ℹ️  {text}")


def test_health_check():
    """Test health check endpoints"""
    print_header("Testing Health Check")
    
    try:
        # Test root endpoint
        response = requests.get(f"{BASE_URL}/")
        print_info(f"Root endpoint: {response.json()}")
        
        # Test health endpoint
        response = requests.get(f"{BASE_URL}/health")
        print_info(f"Health: {response.json()}")
        
        print_success("Health check passed")
        return True
    except Exception as e:
        print_error(f"Health check failed: {e}")
        return False


def test_size_check():
    """Test size check endpoint"""
    print_header("Testing Size Check")
    
    try:
        # Test small file
        print_info("Checking 1MB file...")
        response = requests.post(
            f"{BASE_URL}/api/check-size",
            json={"file_size": 1024 * 1024}
        )
        data = response.json()
        print_info(f"Response: {data}")
        
        if data["allowed"]:
            print_success("1MB file allowed")
        else:
            print_error("1MB file rejected (unexpected)")
        
        # Test large file
        print_info("\nChecking 10GB file...")
        response = requests.post(
            f"{BASE_URL}/api/check-size",
            json={"file_size": 10 * 1024 * 1024 * 1024}
        )
        data = response.json()
        print_info(f"Response: {data}")
        
        if not data["allowed"]:
            print_success("10GB file rejected (expected)")
        else:
            print_error("10GB file allowed (unexpected)")
        
        return True
    except Exception as e:
        print_error(f"Size check failed: {e}")
        return False


def test_upload_and_process(pdf_path, chunk_size=5):
    """Test upload and processing workflow"""
    filename = os.path.basename(pdf_path)
    print_header(f"Testing Upload: {filename}")
    
    try:
        # Check if file exists
        if not os.path.exists(pdf_path):
            print_error(f"File not found: {pdf_path}")
            return None
        
        file_size = os.path.getsize(pdf_path)
        print_info(f"File size: {file_size / 1024:.2f} KB")
        
        # 1. Check size
        print_info("Step 1: Checking file size...")
        size_response = requests.post(
            f"{BASE_URL}/api/check-size",
            json={"file_size": file_size}
        )
        size_data = size_response.json()
        
        if not size_data["allowed"]:
            print_error(f"File too large: {size_data['message']}")
            return None
        
        print_success("Size check passed")
        
        # 2. Upload
        print_info(f"Step 2: Uploading PDF (chunk_size={chunk_size})...")
        with open(pdf_path, "rb") as f:
            upload_response = requests.post(
                f"{BASE_URL}/api/upload",
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"chunk_size": chunk_size}
            )
        
        if upload_response.status_code != 200:
            print_error(f"Upload failed: {upload_response.json()}")
            return None
        
        job_id = upload_response.json()["job_id"]
        print_success(f"Upload successful. Job ID: {job_id}")
        
        # 3. Poll status
        print_info("Step 3: Polling status...")
        max_attempts = 60
        start_time = time.time()
        
        for attempt in range(max_attempts):
            status_response = requests.get(f"{BASE_URL}/api/status/{job_id}")
            
            # Check if response is successful
            if status_response.status_code != 200:
                print(f"   [{attempt+1}/{max_attempts}] Waiting for job to be ready... (HTTP {status_response.status_code})")
                time.sleep(1)
                continue
            
            try:
                status_data = status_response.json()
            except Exception as e:
                print(f"   [{attempt+1}/{max_attempts}] Failed to parse response: {e}")
                time.sleep(1)
                continue
            
            status = status_data.get("status", "unknown")
            progress = status_data.get("progress", 0)
            message = status_data.get("message", "Processing...")
            
            print(f"   [{attempt+1}/{max_attempts}] Status: {status} ({progress}%) - {message}")
            
            if status == "finished":
                elapsed = time.time() - start_time
                print_success(f"Processing completed in {elapsed:.2f} seconds")
                return job_id
            elif status == "error":
                print_error(f"Processing failed: {status_data.get('error', 'Unknown error')}")
                return None
            
            time.sleep(1)
        
        print_error("Timeout waiting for processing to complete")
        return None
        
    except Exception as e:
        print_error(f"Test failed: {e}")
        return None


def test_download(job_id, output_path="downloaded_watermarked.pdf"):
    """Test downloading processed PDF"""
    print_header("Testing Download")
    
    try:
        print_info(f"Downloading job {job_id}...")
        response = requests.get(f"{BASE_URL}/api/download/{job_id}")
        
        if response.status_code != 200:
            print_error(f"Download failed: {response.json()}")
            return False
        
        # Save file
        with open(output_path, "wb") as f:
            f.write(response.content)
        
        file_size = len(response.content)
        print_success(f"Downloaded {file_size / 1024:.2f} KB to {output_path}")
        return True
        
    except Exception as e:
        print_error(f"Download failed: {e}")
        return False


def test_cleanup(job_id):
    """Test cleanup endpoint"""
    print_header("Testing Cleanup")
    
    try:
        print_info(f"Cleaning up job {job_id}...")
        response = requests.delete(f"{BASE_URL}/api/cleanup/{job_id}")
        
        if response.status_code == 200:
            print_success("Cleanup successful")
            return True
        else:
            print_error(f"Cleanup failed: {response.json()}")
            return False
            
    except Exception as e:
        print_error(f"Cleanup failed: {e}")
        return False


def test_error_cases():
    """Test various error cases"""
    print_header("Testing Error Cases")
    
    # Test 1: Invalid job ID
    print_info("Test 1: Getting status for invalid job ID...")
    response = requests.get(f"{BASE_URL}/api/status/invalid-job-id")
    if response.status_code == 404:
        print_success("Correctly rejected invalid job ID")
    else:
        print_error("Should have rejected invalid job ID")
    
    # Test 2: Corrupted PDF (if exists)
    corrupted_path = os.path.join(TEST_DATA_DIR, "corrupted.pdf")
    if os.path.exists(corrupted_path):
        print_info("\nTest 2: Uploading corrupted PDF...")
        with open(corrupted_path, "rb") as f:
            response = requests.post(
                f"{BASE_URL}/api/upload",
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"chunk_size": 5}
            )
        if response.status_code == 400:
            print_success("Correctly rejected corrupted PDF")
            print_info(f"Error message: {response.json()['detail']}")
        else:
            print_error("Should have rejected corrupted PDF")
    
    # Test 3: Encrypted PDF (if exists)
    encrypted_path = os.path.join(TEST_DATA_DIR, "encrypted.pdf")
    if os.path.exists(encrypted_path):
        print_info("\nTest 3: Uploading encrypted PDF...")
        with open(encrypted_path, "rb") as f:
            response = requests.post(
                f"{BASE_URL}/api/upload",
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"chunk_size": 5}
            )
        if response.status_code == 400:
            print_success("Correctly rejected encrypted PDF")
            print_info(f"Error message: {response.json()['detail']}")
        else:
            print_error("Should have rejected encrypted PDF")


def interactive_menu():
    """Interactive menu for testing"""
    while True:
        print_header("WaterMarks Backend - Manual Testing")
        print("\nSelect a test to run:")
        print("1. Health Check")
        print("2. Size Check")
        print("3. Upload & Process (1-page PDF)")
        print("4. Upload & Process (10-page PDF)")
        print("5. Upload & Process (100-page PDF)")
        print("6. Error Cases")
        print("7. Full Workflow (all steps)")
        print("8. Custom PDF file")
        print("9. List all jobs (admin)")
        print("0. Exit")
        
        choice = input("\nEnter choice (0-9): ").strip()
        
        if choice == "0":
            print("Exiting...")
            break
        elif choice == "1":
            test_health_check()
        elif choice == "2":
            test_size_check()
        elif choice == "3":
            pdf_path = os.path.join(TEST_DATA_DIR, "valid_1_page.pdf")
            job_id = test_upload_and_process(pdf_path, chunk_size=5)
            if job_id:
                if input("\nDownload result? (y/n): ").lower() == 'y':
                    test_download(job_id)
                if input("Cleanup? (y/n): ").lower() == 'y':
                    test_cleanup(job_id)
        elif choice == "4":
            pdf_path = os.path.join(TEST_DATA_DIR, "valid_10_pages.pdf")
            job_id = test_upload_and_process(pdf_path, chunk_size=3)
            if job_id:
                if input("\nDownload result? (y/n): ").lower() == 'y':
                    test_download(job_id)
                if input("Cleanup? (y/n): ").lower() == 'y':
                    test_cleanup(job_id)
        elif choice == "5":
            pdf_path = os.path.join(TEST_DATA_DIR, "valid_100_pages.pdf")
            job_id = test_upload_and_process(pdf_path, chunk_size=25)
            if job_id:
                if input("\nDownload result? (y/n): ").lower() == 'y':
                    test_download(job_id)
                if input("Cleanup? (y/n): ").lower() == 'y':
                    test_cleanup(job_id)
        elif choice == "6":
            test_error_cases()
        elif choice == "7":
            pdf_path = os.path.join(TEST_DATA_DIR, "valid_5_pages.pdf")
            print_header("Full Workflow Test")
            
            # All steps
            if test_health_check():
                if test_size_check():
                    job_id = test_upload_and_process(pdf_path, chunk_size=2)
                    if job_id:
                        if test_download(job_id, f"result_{job_id}.pdf"):
                            test_cleanup(job_id)
                            print_success("\n✅ Full workflow completed successfully!")
        elif choice == "8":
            pdf_path = input("Enter path to PDF file: ").strip()
            chunk_size = input("Enter chunk size (default 5): ").strip()
            chunk_size = int(chunk_size) if chunk_size else 5
            
            job_id = test_upload_and_process(pdf_path, chunk_size)
            if job_id:
                if input("\nDownload result? (y/n): ").lower() == 'y':
                    test_download(job_id)
                if input("Cleanup? (y/n): ").lower() == 'y':
                    test_cleanup(job_id)
        elif choice == "9":
            try:
                response = requests.get(f"{BASE_URL}/api/admin/jobs")
                data = response.json()
                print_info(f"\nTotal jobs: {data['total_jobs']}")
                print_info(f"Active jobs: {data['active_jobs']}")
                
                if data['jobs']:
                    print("\nJobs:")
                    for job_id, job_data in data['jobs'].items():
                        print(f"  • {job_id}: {job_data['status']} ({job_data['progress']}%)")
                else:
                    print_info("No jobs found")
                    
            except Exception as e:
                print_error(f"Failed to list jobs: {e}")
        else:
            print_error("Invalid choice")
        
        input("\nPress Enter to continue...")


def main():
    """Main entry point"""
    print("=" * 60)
    print(" WaterMarks Backend - Manual Testing Script")
    print("=" * 60)
    print(f"\nAPI URL: {BASE_URL}")
    print(f"Test Data: {TEST_DATA_DIR}")
    
    # Check if server is running
    print("\n🔍 Checking if server is running...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=3)
        print_success("Server is online!")
    except:
        print_error("Server is not reachable!")
        print_info("Please start the server first: python app.py")
        sys.exit(1)
    
    # Check if test data exists
    if not os.path.exists(TEST_DATA_DIR):
        print_error(f"Test data directory not found: {TEST_DATA_DIR}")
        print_info("Please run: python tests/generate_test_pdfs.py")
        sys.exit(1)
    
    interactive_menu()


if __name__ == "__main__":
    main()
