# WaterMarks Backend

PDF Watermarking Service - Split PDFs into chunks, add colored watermarks in parallel, and merge back together.

## Features

- ✅ Pre-upload file size validation
- ✅ PDF structure validation (corrupted, encrypted detection)
- ✅ Automatic PDF splitting into configurable chunks
- ✅ Parallel watermark processing for speed
- ✅ Different colored watermarks per chunk
- ✅ Real-time job status tracking (uploading → splitting → adding_watermarks → finished)
- ✅ Comprehensive error handling with human-readable messages
- ✅ Memory-safe (prevents server crashes from large files)
- ✅ CORS-enabled for frontend integration

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
```

## Configuration

Edit `.env` or `config.py` for:

- `RAM_SAFETY_MARGIN` - Percentage of RAM to use (default: 0.7)
- `ABSOLUTE_MAX_FILE_SIZE` - Hard limit in bytes (default: 500MB)
- `MAX_PARALLEL_WORKERS` - Concurrent watermark operations (default: 4)
- `WATERMARK_TEXT` - Text for watermarks (default: "WATERMARK")
- `WATERMARK_FONT_SIZE` - Font size (default: 60)
- `WATERMARK_OPACITY` - Opacity 0-1 (default: 0.3)
- `WATERMARK_ROTATION` - Rotation angle (default: 45°)
- `CORS_ORIGINS` - Allowed frontend origins

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

## Deployment on Render

1. **Push code to GitHub**

2. **Create new Web Service on Render**
   - Environment: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`

3. **Set Environment Variables**
   - Add all variables from `.env.example`
   - Adjust RAM_SAFETY_MARGIN based on Render tier

4. **Deploy**

## Error Handling

All errors return human-readable messages:

- **File too large**: "File too large (120MB). Maximum allowed: 300MB"
- **Corrupted PDF**: "The uploaded PDF is corrupted and cannot be processed."
- **Encrypted PDF**: "The PDF is password-protected. Please upload an unencrypted file."
- **Invalid file**: "The uploaded file is not a valid PDF or contains structural errors."

## Project Structure

```
watermarks-backend/
├── app.py                 # FastAPI application
├── config.py              # Configuration settings
├── requirements.txt       # Python dependencies
├── .env.example          # Environment template
├── modules/
│   ├── validator.py      # File validation
│   ├── processor.py      # PDF processing
│   ├── watermark.py      # Watermark operations
│   └── status_manager.py # Job tracking
├── utils/
│   └── helpers.py        # Utility functions
└── temp_files/           # Temporary file storage (auto-created)
    ├── uploads/
    ├── processing/
    └── outputs/
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