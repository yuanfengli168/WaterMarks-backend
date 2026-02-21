# Frontend Integration Guide - Queue System with Progress Tracking

## 🎯 Overview

The backend now implements a **queue system with detailed progress tracking** to prevent memory crashes when processing large PDFs. This guide covers all required frontend changes.

---

## 📋 Summary of Backend Changes

### Core Features
1. **Queue System**: Jobs are processed serially (one at a time) to prevent memory exhaustion
2. **Session Tracking**: Each user can have max 1 active job (tracked via secure cookies)
3. **Enhanced Progress**: Smooth 0-100% progress including merge phase (80-100%)
4. **1-Minute Download Window**: Files auto-delete 1 minute after processing OR after first download
5. **Dynamic Capacity**: Queue accepts jobs based on available RAM and disk space

### New/Changed Status Values
- `"queued"` - Job waiting in line (new)
- `"processing"` - Reading PDF and preparing
- `"splitting"` - Splitting PDF into chunks
- `"adding_watermarks"` - Adding watermarks to chunks
- `"merging"` - Merging chunks back together (NEW: now reports 80-100% progress)
- `"finished"` - Ready to download (1-minute window starts)
- `"error"` - Processing failed

---

## 🔧 Required Frontend Changes

### 1. Handle Session Cookies ✅

**No action required** - browsers automatically handle the `session_id` cookie.

Just ensure fetch requests include credentials:
```javascript
fetch('/api/upload', {
  method: 'POST',
  body: formData,
  credentials: 'include'  // ← REQUIRED for cookies
});
```

---

### 2. Handle 503 "Server Busy" Response

**When:** Upload endpoint returns `503` status

**Scenarios:**
- Queue is at capacity (based on disk space/RAM)
- User already has an active job processing

**Response structure:**
```json
{
  "message": "Queue is at capacity. Try again later.",
  "retry_after_seconds": 180
}
```

**Frontend implementation:**
```javascript
async function uploadFile(file, chunkSize) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('chunk_size', chunkSize);
  
  const response = await fetch('/api/upload', {
    method: 'POST',
    body: formData,
    credentials: 'include'
  });
  
  // Handle server busy
  if (response.status === 503) {
    const data = await response.json();
    const waitMinutes = Math.ceil(data.retry_after_seconds / 60);
    
    showError(`Server is busy. ${data.message} Please try again in ${waitMinutes} minute(s).`);
    
    // Optional: Auto-retry after specified time
    setTimeout(() => {
      showNotification('Server may be ready now. Try uploading again.');
    }, data.retry_after_seconds * 1000);
    
    return null;
  }
  
  if (!response.ok) {
    throw new Error('Upload failed');
  }
  
  const data = await response.json();
  return data.job_id;
}
```

---

### 3. Handle Queue Status & Display Progress

**Key change:** Progress now reports smoothly from 0-100%, including merge phase.

**Progress ranges:**
- `0%` - Job queued
- `1-30%` - Splitting PDF into chunks
- `31-79%` - Adding watermarks to each chunk
- `80-95%` - Merging chunks (appending)
- `95-100%` - Merging chunks (writing file)
- `100%` - Finished

**TypeScript Interface:**
```typescript
interface StatusResponse {
  job_id: string;
  status: 'queued' | 'processing' | 'splitting' | 'adding_watermarks' | 'merging' | 'finished' | 'error';
  progress: number;  // 0-100
  message: string;
  
  // Only present when status === 'queued':
  queue_position?: number;           // Position in queue (1, 2, 3...)
  jobs_ahead?: number;               // Number of jobs ahead (0, 1, 2...)
  estimated_wait_seconds?: number;   // Estimated wait time
  estimated_start_time?: string;     // ISO timestamp when job starts
  
  // Only present when status === 'finished':
  result_path?: string;
  
  // Only present when status === 'error':
  error?: string;
}
```

**Frontend implementation:**
```javascript
function startStatusPolling(jobId) {
  const interval = setInterval(async () => {
    try {
      const response = await fetch(`/api/status/${jobId}`);
      const data = await response.json();
      
      switch (data.status) {
        case 'queued':
          handleQueuedStatus(data);
          break;
          
        case 'processing':
        case 'splitting':
        case 'adding_watermarks':
        case 'merging':  // NEW: Merge now has progress 80-100%
          handleProcessingStatus(data);
          break;
          
        case 'finished':
          clearInterval(interval);
          handleFinishedStatus(data);
          break;
          
        case 'error':
          clearInterval(interval);
          handleErrorStatus(data);
          break;
      }
    } catch (error) {
      console.error('Polling error:', error);
    }
  }, 1000);  // Poll every 1 second
  
  return interval;
}

function handleQueuedStatus(data) {
  // Show queue position
  updateStatus(`Queue Position: ${data.queue_position}`);
  
  // Show jobs ahead (will be 0, 1, 2, etc.)
  const jobsText = data.jobs_ahead === 1 ? '1 job' : `${data.jobs_ahead} jobs`;
  updateDetails(`${jobsText} ahead of you`);
  
  // Show estimated wait time
  const waitMinutes = Math.ceil(data.estimated_wait_seconds / 60);
  updateWaitTime(`Estimated wait: ${waitMinutes} minute(s)`);
  
  // Progress bar at 0%
  updateProgressBar(0);
}

function handleProcessingStatus(data) {
  // Show current phase
  updateStatus(data.message);
  
  // Update progress bar (now includes merge phase 80-100%)
  updateProgressBar(data.progress);
  
  // Show percentage
  updatePercentage(`${data.progress}%`);
  
  // Optional: Show phase-specific messages
  if (data.status === 'merging' && data.progress >= 80) {
    updateDetails('Merging chunks back into final PDF...');
  }
}

function handleFinishedStatus(data) {
  updateStatus('✅ Processing complete!');
  updateProgressBar(100);
  
  // CRITICAL: Show 1-minute warning
  showWarning({
    title: 'Download Ready!',
    message: 'Your file is ready. Download within 1 minute or it will be automatically deleted.',
    type: 'warning',
    urgent: true
  });
  
  // Enable download button
  enableDownloadButton(data.job_id);
  
  // Optional: Show countdown timer
  startDownloadCountdown(60);  // 60 seconds
}

function handleErrorStatus(data) {
  updateStatus('❌ Processing failed');
  showError(data.error || data.message);
  
  // Re-enable upload form
  resetUploadForm();
}
```

---

### 4. Handle 1-Minute Download Window

**Critical:** Files are deleted either:
1. Immediately after first successful download (200 OK), OR
2. Exactly 1 minute after job finishes (if not downloaded)

**Frontend must:**
- Show prominent warning when status becomes `"finished"`
- Display countdown timer (optional but recommended)
- Handle 410 Gone response if window expired

```javascript
async function downloadFile(jobId) {
  try {
    showLoading('Downloading...');
    
    const response = await fetch(`/api/download/${jobId}`);
    
    // Handle expired download window
    if (response.status === 410) {
      const data = await response.json();
      showError('❌ Download window expired (1 minute limit). Please upload and process your file again.');
      resetToUploadForm();
      return;
    }
    
    if (!response.ok) {
      throw new Error(`Download failed: ${response.status}`);
    }
    
    // Download successful
    const blob = await response.blob();
    
    // Verify file isn't corrupted
    if (blob.size < 1000) {
      throw new Error('Downloaded file is too small - may be corrupted');
    }
    
    // Save file to user's computer
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `watermarked_${Date.now()}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showSuccess('✅ Download complete! File has been deleted from server.');
    
    // Note: File is now permanently deleted from server
    disableDownloadButton();
    
    // Allow new upload
    resetToUploadForm();
    
  } catch (error) {
    console.error('Download error:', error);
    showError('Download failed. The file may have been deleted. Please resubmit your PDF.');
    resetToUploadForm();
  }
}

// Optional: Countdown timer
function startDownloadCountdown(seconds) {
  let remaining = seconds;
  
  const timer = setInterval(() => {
    remaining--;
    updateCountdown(`${remaining}s remaining`);
    
    if (remaining <= 10) {
      // Highlight urgency in last 10 seconds
      showUrgentWarning(`URGENT: ${remaining}s remaining!`);
    }
    
    if (remaining <= 0) {
      clearInterval(timer);
      showError('Download window expired. File has been deleted.');
      disableDownloadButton();
      resetToUploadForm();
    }
  }, 1000);
  
  // Store timer ID to cancel if user downloads early
  return timer;
}
```

---

### 5. Prevent Multiple Uploads Per Session

**Backend enforces:** Maximum 1 active job per session

**Frontend should:**
- Disable upload form while job is active
- Show current job status prominently
- Only re-enable after download/error

```javascript
class UploadManager {
  constructor() {
    this.activeJobId = null;
    this.pollingInterval = null;
  }
  
  async startUpload(file, chunkSize) {
    // Prevent multiple uploads
    if (this.activeJobId) {
      showError('You already have a file being processed. Please wait for it to complete.');
      return;
    }
    
    // Upload file
    const jobId = await uploadFile(file, chunkSize);
    
    if (!jobId) {
      return;  // Upload failed (503 or other error)
    }
    
    // Track active job
    this.activeJobId = jobId;
    
    // Disable upload UI
    disableUploadForm();
    
    // Start polling
    this.pollingInterval = startStatusPolling(jobId);
  }
  
  handleJobComplete() {
    // Clear active job
    this.activeJobId = null;
    
    // Stop polling
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
    
    // Re-enable upload form
    enableUploadForm();
  }
}
```

---

## 🔄 Complete Status Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. USER UPLOADS FILE                                        │
│    POST /api/upload                                         │
│    → Returns job_id OR 503 (server busy)                    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. QUEUED (if other jobs ahead)                             │
│    Status: "queued"                                         │
│    Progress: 0%                                             │
│    Fields: queue_position, jobs_ahead, estimated_wait       │
│    UI: Show "Position X, Y jobs ahead, ~Z minutes"         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. PROCESSING PHASES                                        │
│    Status: "processing" → "splitting" → "adding_watermarks" │
│    Progress: 1% → 30% → 79%                                 │
│    UI: Show progress bar + percentage                       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. MERGING (NEW: Detailed progress)                         │
│    Status: "merging"                                        │
│    Progress: 80% → 95% → 100%                               │
│    UI: "Merging chunks (85%)"                               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. FINISHED                                                 │
│    Status: "finished"                                       │
│    Progress: 100%                                           │
│    UI: Show download button + 1-minute warning              │
│    👉 START 60-SECOND COUNTDOWN                             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. DOWNLOAD                                                 │
│    GET /api/download/{job_id}                               │
│    → File sent + immediately deleted from server            │
│    OR                                                       │
│    → 410 Gone (if 1 minute passed)                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 📝 Example: Complete Implementation

```javascript
// Full example with error handling
class PDFWatermarkApp {
  constructor() {
    this.activeJobId = null;
    this.pollingInterval = null;
    this.downloadTimer = null;
  }
  
  async handleFileUpload(file, chunkSize) {
    if (this.activeJobId) {
      alert('Please wait for current job to complete');
      return;
    }
    
    try {
      // Upload
      const formData = new FormData();
      formData.append('file', file);
      formData.append('chunk_size', chunkSize);
      
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
        credentials: 'include'
      });
      
      // Server busy?
      if (response.status === 503) {
        const data = await response.json();
        const waitMin = Math.ceil(data.retry_after_seconds / 60);
        alert(`Server busy: ${data.message}\nTry again in ${waitMin} minutes.`);
        return;
      }
      
      if (!response.ok) {
        throw new Error('Upload failed');
      }
      
      const data = await response.json();
      this.startTracking(data.job_id);
      
    } catch (error) {
      alert(`Upload error: ${error.message}`);
    }
  }
  
  startTracking(jobId) {
    this.activeJobId = jobId;
    this.disableUpload();
    
    this.pollingInterval = setInterval(() => this.pollStatus(jobId), 1000);
  }
  
  async pollStatus(jobId) {
    try {
      const response = await fetch(`/api/status/${jobId}`);
      const data = await response.json();
      
      // Update UI based on status
      this.updateUI(data);
      
      // Stop polling when done
      if (data.status === 'finished') {
        clearInterval(this.pollingInterval);
        this.handleFinished(data);
      } else if (data.status === 'error') {
        clearInterval(this.pollingInterval);
        this.handleError(data);
      }
      
    } catch (error) {
      console.error('Poll error:', error);
    }
  }
  
  updateUI(data) {
    const statusEl = document.getElementById('status');
    const progressEl = document.getElementById('progress');
    const detailsEl = document.getElementById('details');
    
    if (data.status === 'queued') {
      statusEl.textContent = `Queue Position: ${data.queue_position}`;
      detailsEl.textContent = `${data.jobs_ahead} ahead, ~${Math.ceil(data.estimated_wait_seconds / 60)} min`;
      progressEl.value = 0;
    } else {
      statusEl.textContent = data.message;
      progressEl.value = data.progress;
      detailsEl.textContent = `${data.progress}% complete`;
    }
  }
  
  handleFinished(data) {
    document.getElementById('status').textContent = '✅ Ready to download!';
    document.getElementById('progress').value = 100;
    
    // Show urgent warning
    const warning = document.getElementById('warning');
    warning.textContent = '⚠️ Download within 1 minute or file will be deleted!';
    warning.style.display = 'block';
    warning.style.color = 'red';
    
    // Enable download
    const downloadBtn = document.getElementById('downloadBtn');
    downloadBtn.disabled = false;
    downloadBtn.onclick = () => this.download(data.job_id);
    
    // Start countdown
    this.startCountdown(60);
  }
  
  startCountdown(seconds) {
    let remaining = seconds;
    const countdownEl = document.getElementById('countdown');
    
    this.downloadTimer = setInterval(() => {
      remaining--;
      countdownEl.textContent = `${remaining}s remaining`;
      
      if (remaining <= 0) {
        clearInterval(this.downloadTimer);
        alert('Download window expired. File deleted.');
        this.reset();
      }
    }, 1000);
  }
  
  async download(jobId) {
    try {
      const response = await fetch(`/api/download/${jobId}`);
      
      if (response.status === 410) {
        alert('Download expired. Please upload again.');
        this.reset();
        return;
      }
      
      if (!response.ok) {
        throw new Error('Download failed');
      }
      
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `watermarked_${Date.now()}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      
      alert('✅ Download complete! File deleted from server.');
      this.reset();
      
    } catch (error) {
      alert(`Download error: ${error.message}`);
      this.reset();
    }
  }
  
  handleError(data) {
    alert(`❌ Error: ${data.error || data.message}`);
    this.reset();
  }
  
  reset() {
    this.activeJobId = null;
    
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
    
    if (this.downloadTimer) {
      clearInterval(this.downloadTimer);
      this.downloadTimer = null;
    }
    
    this.enableUpload();
    document.getElementById('warning').style.display = 'none';
    document.getElementById('downloadBtn').disabled = true;
  }
  
  disableUpload() {
    document.getElementById('uploadBtn').disabled = true;
    document.getElementById('fileInput').disabled = true;
  }
  
  enableUpload() {
    document.getElementById('uploadBtn').disabled = false;
    document.getElementById('fileInput').disabled = false;
  }
}

// Usage
const app = new PDFWatermarkApp();
document.getElementById('uploadBtn').onclick = () => {
  const fileInput = document.getElementById('fileInput');
  const chunkSize = parseInt(document.getElementById('chunkSize').value);
  app.handleFileUpload(fileInput.files[0], chunkSize);
};
```

---

## ✅ Testing Checklist

### Basic Flow
- [ ] Upload small PDF → processes immediately (no queue)
- [ ] Upload shows progress from 0% → 100% smoothly
- [ ] Merge phase shows progress from 80% → 100%
- [ ] Download button appears with 1-minute warning
- [ ] Download works and file is deleted

### Queue Behavior
- [ ] Upload 3 files quickly → 1st processes, 2nd/3rd queued
- [ ] Queue position shows correctly ("Position 2, 1 job ahead")
- [ ] Jobs process in order (FIFO)
- [ ] Estimated wait time updates as queue progresses

### Server Capacity
- [ ] Upload when server busy → 503 response with retry_after
- [ ] Try 2nd upload while 1st active → rejected with message

### Download Window
- [ ] Download immediately after finish → works
- [ ] Wait 61+ seconds → download returns 410 Gone
- [ ] Download twice → 2nd attempt returns 410

### Error Handling
- [ ] Network error during poll → doesn't break UI
- [ ] Invalid file → shows error message
- [ ] Memory error → shows friendly message

### Session Management
- [ ] Close browser and reopen → new session (can upload)
- [ ] Multiple tabs same browser → share session (one job max)
- [ ] Different browsers → different sessions (independent)

---

## 📊 API Reference Summary

### POST /api/upload
**Request:**
```
Content-Type: multipart/form-data
file: [PDF binary]
chunk_size: [integer]
```

**Success (200):**
```json
{
  "job_id": "abc123",
  "message": "Upload successful. Processing queued."
}
```

**Server Busy (503):**
```json
{
  "message": "Queue is at capacity. Try again later.",
  "retry_after_seconds": 180
}
```

---

### GET /api/status/{job_id}
**Success (200):**
```json
{
  "job_id": "abc123",
  "status": "merging",
  "progress": 85,
  "message": "Merging chunks (85%)",
  
  // If queued:
  "queue_position": 2,
  "jobs_ahead": 1,
  "estimated_wait_seconds": 120,
  "estimated_start_time": "2026-02-21T15:30:00"
}
```

---

### GET /api/download/{job_id}
**Success (200):**
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="watermarked.pdf"
[PDF binary data]
```

**Expired (410):**
```json
{
  "error": "Download window expired (1 minute limit). Please resubmit."
}
```

---

## 🚀 Key Differences from Previous Version

| Feature | Old Behavior | New Behavior |
|---------|-------------|--------------|
| Merge Progress | Status "merging" with no progress | Status "merging" with 80-100% progress |
| Progress Smoothness | Jumped from 79% to 100% | Smooth progression 79% → 85% → 95% → 100% |
| Merge Logging | 73x "merging" status spam | Single status with incremental progress |
| Timeout | No timeout (could hang forever) | Relies on infrastructure timeout |
| Queue Position | jobs_ahead = position - 1 | Still position - 1 (0 means none ahead) |

---

## 💡 Best Practices

1. **Always poll at 1-second intervals** (not faster, not slower)
2. **Show countdown timer** for download window (improves UX)
3. **Disable upload form** while job is active (prevents confusion)
4. **Include `credentials: 'include'`** in all fetch requests (required for sessions)
5. **Handle 503 gracefully** with retry time (don't just show error)
6. **Verify blob size** after download (detect corruption early)
7. **Show clear error messages** (don't just say "failed")
8. **Test with large files** (1000+ page PDFs reveal edge cases)

---

## 🆘 Troubleshooting

**Q: Progress stuck at 79%?**
A: This is expected if file has many chunks. Merge phase (80-100%) can take several minutes for large files. Progress should increment gradually.

**Q: Download returns 410 immediately?**
A: Check if you're polling too fast or if backend crash caused job loss. Verify backend logs.

**Q: Upload always returns 503?**
A: Server may be out of disk space or memory. Check backend health endpoint or Render logs.

**Q: Queue position not updating?**
A: Ensure you're polling every 1 second. Position updates as jobs complete.

**Q: Download file is 0 bytes?**
A: Backend may have crashed during merge. Check Render logs for memory errors.

---

## 📞 Support

If you encounter issues:
1. Check browser console for errors
2. Check network tab for API responses
3. Verify backend logs on Render dashboard
4. Test with small PDF first (< 10MB, < 100 pages)

---

**That's everything!** The backend now handles queue management and provides smooth progress tracking including the merge phase (80-100%). Frontend just needs to display the information and handle the 1-minute download window.
