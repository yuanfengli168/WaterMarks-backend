# API Documentation

## WaterMarks Backend REST API

Base URL: `http://localhost:8000` (or your deployment URL)

Interactive docs: `http://localhost:8000/docs`

---

## Endpoints

### Health Check

#### GET `/`
Root endpoint - returns service information

**Response:**
```json
{
  "service": "WaterMarks Backend",
  "status": "online",
  "version": "1.0.0"
}
```

#### GET `/health`
Health check with server status

**Response:**
```json
{
  "status": "healthy",
  "active_jobs": 2
}
```

---

### Main Workflow Endpoints

#### POST `/api/check-size`
Pre-upload file size validation (call this BEFORE uploading)

**Request Body:**
```json
{
  "file_size": 1048576
}
```

**Response (200 OK):**
```json
{
  "allowed": true,
  "max_allowed_size": 314572800,
  "available_ram": 512000000,
  "message": "File size is acceptable"
}
```

**Response (200 OK - Rejected):**
```json
{
  "allowed": false,
  "max_allowed_size": 314572800,
  "available_ram": 512000000,
  "message": "File too large (500.0 MB). Maximum allowed: 300.0 MB"
}
```

---

#### POST `/api/upload`
Upload PDF file for processing

**Request (multipart/form-data):**
- `file`: PDF file (required)
- `chunk_size`: integer, pages per chunk (default: 10)

**Response (200 OK):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "File uploaded successfully. Processing started."
}
```

**Error Responses:**
- `400 Bad Request`: Invalid file type or corrupted PDF
- `413 Payload Too Large`: File exceeds size limit
- `500 Internal Server Error`: Server error

**Error Examples:**
```json
{
  "detail": "The uploaded PDF is corrupted and cannot be processed."
}
```

```json
{
  "detail": "The PDF is password-protected. Please upload an unencrypted file."
}
```

---

#### GET `/api/status/{job_id}`
Get current processing status

**Parameters:**
- `job_id`: Job identifier (from upload response)

**Response (200 OK):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "adding_watermarks",
  "progress": 50,
  "message": "Adding watermarks to chunks",
  "result_path": null,
  "error": null
}
```

**Status Values:**
- `uploading` (progress: 10%) - File is being uploaded
- `splitting` (progress: 30%) - PDF is being split into chunks
- `adding_watermarks` (progress: 50%) - Watermarks being applied
- `merging` (progress: 80%) - Chunks being merged back
- `finished` (progress: 100%) - Processing complete
- `error` (progress: 0%) - An error occurred

**Error Response (404 Not Found):**
```json
{
  "detail": "Job not found"
}
```

---

#### GET `/api/download/{job_id}`
Download processed PDF

**Parameters:**
- `job_id`: Job identifier

**Response (200 OK):**
- Content-Type: `application/pdf`
- File download

**Error Responses:**
- `404 Not Found`: Job or file not found
- `400 Bad Request`: Job not finished yet

```json
{
  "detail": "Job not ready. Current status: adding_watermarks"
}
```

---

#### DELETE `/api/cleanup/{job_id}`
Clean up job files and remove from tracking

**Parameters:**
- `job_id`: Job identifier

**Response (200 OK):**
```json
{
  "message": "Job 550e8400-e29b-41d4-a716-446655440000 cleaned up successfully"
}
```

---

### Admin Endpoints

#### GET `/api/admin/jobs`
List all jobs (debugging/monitoring)

**Response:**
```json
{
  "total_jobs": 5,
  "active_jobs": 2,
  "jobs": {
    "job-id-1": {
      "job_id": "job-id-1",
      "status": "finished",
      "progress": 100,
      "message": "PDF processed successfully",
      "created_at": "2026-02-20T10:30:00",
      "updated_at": "2026-02-20T10:31:45"
    }
  }
}
```

#### POST `/api/admin/cleanup-old`
Remove jobs older than retention time

**Response:**
```json
{
  "message": "Cleaned up 3 old jobs"
}
```

---

## Workflow Example

### 1. Check File Size
```bash
curl -X POST http://localhost:8000/api/check-size \
  -H "Content-Type: application/json" \
  -d '{"file_size": 2097152}'
```

### 2. Upload PDF (if size check passes)
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@document.pdf" \
  -F "chunk_size=5"
```

Response: `{"job_id": "abc-123", "message": "..."}`

### 3. Poll Status
```bash
# Poll every 1-2 seconds until status is "finished"
curl http://localhost:8000/api/status/abc-123
```

### 4. Download Result
```bash
curl -O http://localhost:8000/api/download/abc-123
```

### 5. Cleanup (optional)
```bash
curl -X DELETE http://localhost:8000/api/cleanup/abc-123
```

---

## Error Codes

- `200 OK` - Success
- `400 Bad Request` - Invalid input or corrupted file
- `404 Not Found` - Job or resource not found
- `413 Payload Too Large` - File exceeds size limit
- `500 Internal Server Error` - Server error

---

## Configuration

See `.env.example` for configurable parameters:
- File size limits
- Watermark appearance (text, color, opacity, rotation)
- Processing limits (parallel workers)
- CORS origins
- Retention time

---

## Rate Limiting

Currently not implemented. For production use, consider adding rate limiting middleware.

## Authentication

Currently not implemented. For production use, consider adding API key authentication.
