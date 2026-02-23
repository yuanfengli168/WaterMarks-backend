# PDF Watermark Backend API

A FastAPI-based backend service for adding watermarks to PDF files with chunking, parallel processing, and real-time status tracking.

## Features

- ✅ **Pre-upload size checking** - Validate file size before upload to prevent server crashes
- ✅ **RAM-aware processing** - Rejects files that would exceed available memory (70% safety margin)
- ✅ **Parallel watermarking** - Splits PDFs into chunks and processes them concurrently
- ✅ **Real-time status tracking** - 4-phase progress updates (uploading → splitting → adding_watermarks → finished)
- ✅ **PDF validation** - Detects corrupted, encrypted, or fake PDFs
- ✅ **Error handling** - Human-readable error messages for frontend display
- ✅ **Background processing** - Non-blocking API with job-based workflow
- ✅ **Health monitoring** - Memory stats and uptime endpoints for deployment
- ✅ **CORS-enabled** - Configured for GitHub Pages and custom domains
- ✅ **Fully tested** - 73 automated tests covering all functionality

## Architecture

### Modules

1. **Validator Module** (`modules/validator.py`)
   - Pre-upload size checking
   - PDF validation (structure, encryption, corruption)
   - Human-readable error messages

2. **Processor Module** (`modules/processor.py`)
   - PDF splitting into chunks
   - Parallel watermark orchestration
   - PDF merging

3. **Watermark Module** (`modules/watermark.py`)
   - Watermark creation with reportlab
   - Color management per chunk
   - Watermark application to PDFs

4. **Status Manager Module** (`modules/status_manager.py`)
   - Thread-safe job tracking
   - Status updates (uploading, splitting, adding_watermarks, finished)
   - Automatic cleanup of old jobs

## API Endpoints

### 1. Check File Size (Pre-Upload)
```
POST /api/check-size
Body: { "file_size": 1234567 }
Response: { "allowed": true, "max_allowed_size": 314572800, "message": "..." }
```

### 2. Upload PDF
```
POST /api/upload
Form Data:
  - file: PDF file
  - chunk_size: integer (pages per chunk)
Response: { "job_id": "uuid", "message": "..." }
```

### 3. Check Job Status
```
GET /api/status/{job_id}
Response: {
  "job_id": "uuid",
  "status": "uploading|splitting|adding_watermarks|finished|error",
  "progress": 0-100,
  "message": "..."
}
```

### 4. Download Result
```
GET /api/download/{job_id}
Response: PDF file
```

### 5. Cleanup Job
```
DELETE /api/cleanup/{job_id}
Response: { "message": "..." }
```

### Admin Endpoints
```
GET /api/admin/jobs - List all jobs
POST /api/admin/cleanup-old - Clean up old jobs
```

## Installation

### Prerequisites
- Python 3.8+
- pip

### Setup

1. **Clone repository**
```bash
git clone <repo-url>
cd WaterMarks-backend
```

2. **Create virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your settings
```

5. **Run the server**
```bash
python app.py
```

Or with uvicorn:
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
# if in use, can kill
lsof -ti :8000 | xargs kill -9 2>/dev/null;
```

## Configuration

Key environment variables in `.env`:

```bash
# File size limits (adjust based on server RAM)
ABSOLUTE_MAX_FILE_SIZE=5242880  # 5MB for Render free tier (512MB RAM, 3 concurrent jobs)
RAM_SAFETY_MARGIN=0.7
MIN_FREE_RAM_REQUIRED=104857600   # 100MB

# Processing
MAX_PARALLEL_WORKERS=2  # Reduce for free tier
DEFAULT_CHUNK_SIZE=10
MAX_CONCURRENT_JOBS=3  # Safe for 512MB RAM with 5MB files

# Watermark customization
WATERMARK_TEXT=WATERMARK
WATERMARK_FONT_SIZE=60
WATERMARK_OPACITY=0.3
WATERMARK_ROTATION=45

# CORS - Add your frontend URLs
CORS_ORIGINS=http://localhost:3000,https://yourusername.github.io

# Debug mode
DEBUG=False  # Set to True for development
```

See [.env.example](.env.example) for all available options and production recommendations.

## Usage Example

### Using cURL

**1. Check file size:**
```bash
curl -X POST http://localhost:8000/api/check-size \
  -H "Content-Type: application/json" \
  -d '{"file_size": 1048576}'
```

**2. Upload PDF:**
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@document.pdf" \
  -F "chunk_size=10"
```

**3. Check status:**
```bash
curl http://localhost:8000/api/status/{job_id}
```

**4. Download result:**
```bash
curl -O http://localhost:8000/api/download/{job_id}
```

### Using Python

```python
import requests

# Check size
response = requests.post('http://localhost:8000/api/check-size',
                        json={'file_size': 1048576})
print(response.json())

# Upload
with open('document.pdf', 'rb') as f:
    response = requests.post('http://localhost:8000/api/upload',
                           files={'file': f},
                           data={'chunk_size': 10})
    job_id = response.json()['job_id']

# Poll status
import time
while True:
    response = requests.get(f'http://localhost:8000/api/status/{job_id}')
    status = response.json()['status']
    print(f"Status: {status}")
    if status == 'finished':
        break
    time.sleep(1)

# Download
response = requests.get(f'http://localhost:8000/api/download/{job_id}')
with open('watermarked.pdf', 'wb') as f:
    f.write(response.content)
```

## Quick Start

### Local Development

1. **Clone and setup**:
```bash
git clone <your-repo-url>
cd WaterMarks-backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

2. **Run the server**:
```bash
python app.py
```

3. **Access the API**:
   - API: `http://localhost:8000`
   - Interactive docs: `http://localhost:8000/docs`

### Production Deployment

**Deploy to Render** (recommended for free hosting):

📖 See [DEPLOYMENT.md](DEPLOYMENT.md) for comprehensive deployment guide including:
- Step-by-step Render setup instructions
- Environment variable configuration
- CORS setup for GitHub Pages
- Free tier considerations and optimizations
- Troubleshooting guide
- Custom domain setup

**Quick deploy with `render.yaml`**:
```bash
# 1. Push to GitHub
git add .
git commit -m "Deploy to Render"
git push origin main

# 2. Connect to Render and it will auto-deploy using render.yaml
```

## Monitoring Endpoints

- `GET /health` - Health check with memory stats and active jobs count
- `GET /ping` - Simple wake-up endpoint (useful for free tier spin-down management)

## Testing

**Generate Test Files:**

```bash
# Create 9 different test PDFs (valid, corrupted, encrypted, etc.)
python tests/generate_test_pdfs.py

# Create large 520MB PDF for stress testing
python tests/generate_large_pdf.py
```

**Run Tests:**

```bash
# Automated test suite (73 tests)
./run_tests.sh  # Auto-activates venv and runs pytest

# Or manually
source venv/bin/activate
pytest -v

# Manual interactive testing
python tests/manual_test.py
```

## Frontend Integration

📖 See [FRONTEND_API_DOCUMENTATION.md](FRONTEND_API_DOCUMENTATION.md) for detailed integration guide including:
- Complete request/response formats
- Error handling best practices
- Example code snippets (fetch API)
- Status polling strategies
- File download handling

## Workflow

```
1. Frontend → POST /api/check-size (file_size in bytes)
   Backend → Validates against available RAM
   
2. If accepted:
   Frontend → POST /api/upload (multipart/form-data with PDF)
   Backend → Returns job_id, starts background processing
   
3. Background processing:
   - Splits PDF into chunks
   - Watermarks chunks in parallel (multi-threaded)
   - Merges chunks back together
   
4. Frontend → GET /api/status/{job_id} (poll every 1-2 seconds)
   Backend → Returns progress: uploading → splitting → adding_watermarks → finished
   
5. When finished:
   Frontend → GET /api/download/{job_id}
   Backend → Returns watermarked PDF
   
6. Cleanup:
   Frontend → DELETE /api/{job_id}
   Backend → Removes temp files
```

## Error Handling

All errors return human-readable messages:

- **File too large**: "File too large (120MB). Maximum allowed: 300MB based on available server memory (450MB)"
- **Corrupted PDF**: "The uploaded PDF is corrupted and cannot be processed."
- **Encrypted PDF**: "The PDF is password-protected. Please upload an unencrypted file."
- **Invalid file**: "The uploaded file is not a valid PDF or contains structural errors."
- **Memory insufficient**: "Server memory insufficient to process this file safely."
- **Job not found**: "Job not found - it may have been cleaned up or expired."

## Performance Considerations

### Memory Management[config.py](config.py)
2. **Custom watermark styles**: Modify `create_watermark_overlay()` in [modules/watermark.py](modules/watermark.py)
3. **New endpoints**: Add to [app.py](app.py) and follow FastAPI routing patterns
4. **Adjust memory limits**: Modify `RAM_SAFETY_MARGIN` and `ABSOLUTE_MAX_FILE_SIZE` in `.env`
- Processes chunks concurrently using ThreadPoolExecutor
- Configurable worker count (adjust for server capacity)
- Each chunk gets a different colored watermark for visual verification

### Free Tier Recommendations
When deploying on free hosting (e.g., Render Free with 512MB RAM):
- Set `ABSOLUTE_MAX_FILE_SIZE=5242880` (5MB)
- Set `MAX_PARALLEL_WORKERS=2`
- Set `MAX_CONCURRENT_JOBS=3`
- Implement frontend wake-up call using `/ping` endpoint to handle cold starts

## Technology Stack

- **FastAPI** - Modern async web framework with auto-generated OpenAPI docs
- **PyPDF2** - PDF manipulation (split/merge/read)
- **reportlab** - Watermark generation with custom text, colors, rotation
- **psutil** - System memory monitoring for RAM-aware processing
- **Threading** - Parallel chunk processing with ThreadPoolExecutor
- **Pydantic** - Request/response validation and serialization
- **pytest** - Testing framework with 73 comprehensive tests
- **uvicorn/gunicorn** - ASGI server for production deployment

## Project Structure

```
WaterMarks-backend/
├── app.py                          # FastAPI application with all endpoints
├── config.py                       # Configuration settings and environment variables
├── requirements.txt                # Python dependencies
├── .env.example                   # Environment template with production notes
├── render.yaml                     # Render deployment configuration
├── DEPLOYMENT.md                   # Comprehensive deployment guide
├── FRONTEND_API_DOCUMENTATION.md   # Frontend integration guide
├── modules/
│   ├── validator.py               # File validation and PDF structure checking
│   ├── processor.py               # PDF splitting, parallel processing, merging
│   ├── watermark.py               # Watermark creation and application
│   └── status_manager.py          # Thread-safe job tracking and status updates
├── utils/
│   └── helpers.py                 # Utility functions
├── tests/
│   ├── test_validator.py          # Unit tests for validator module
│   ├── test_processor.py          # Unit tests for processor module
│   ├── test_watermark.py          # Unit tests for watermark module
│   ├── test_status_manager.py     # Unit tests for status manager
│   ├── test_integration.py        # End-to-end integration tests
│   ├── generate_test_pdfs.py      # Generate 9 different test PDFs
│   ├── generate_large_pdf.py      # Generate 520MB test file
│   └── manual_test.py             # Interactive CLI testing tool
├── run_tests.sh                   # Test runner with venv activation
└── temp_files/                    # Temporary file storage (auto-created)
    ├── uploads/                   # Uploaded PDFs
    ├── processing/                # Intermediate chunks
    └── outputs/                   # Watermarked results
```

## Development

### Adding New Features

1. **New watermark colors**: Edit `WATERMARK_COLORS` in `config.py`
2. **Custom watermark styles**: Modify `create_watermark_overlay()` in `modules/watermark.py`
3. **New endpoints**: Add to `app.py`

### Testing

Tests will be added in a separate phase. See `tests/` directory (coming soon).

## License

MIT License

## Support

For issues or questions, please open a GitHub issue.