# Frontend Integration Guide - Queue System Update

## Summary of Backend Changes

The backend now uses a **queue system** to prevent server crashes. Key changes:

1. **New status**: `"queued"` (job waiting in line)
2. **Session tracking**: Users identified via cookies (one PDF per user at a time)
3. **Server busy**: Upload can return `503` when at capacity
4. **1-minute download window**: Files deleted 1 minute after processing OR immediately after download
5. **Dynamic queue**: Accepts jobs based on available disk space and RAM

---

## Required Frontend Changes

### 1. Handle Session Cookies ✅

**No action required** - Browser automatically handles `session_id` cookie.

---

### 2. Handle 503 "Server Busy" Response

**When:** Upload fails with `503` status code

**Old behavior:** Upload always succeeded or returned `400/500`

**New behavior:**
```javascript
// Upload request
const response = await fetch('/api/upload', {
  method: 'POST',
  body: formData
});

if (response.status === 503) {
  const data = await response.json();
  // Show friendly error with retry time
  showError(`${data.message} Try again in ${Math.ceil(data.retry_after_seconds / 60)} minutes.`);
  
  // Optional: Auto-retry after specified time
  setTimeout(() => {
    showMessage('Server may be ready now. Please try uploading again.');
  }, data.retry_after_seconds * 1000);
  
  return;
}

// Normal success
const data = await response.json();
const jobId = data.job_id;
```

---

### 3. Handle "queued" Status

**When:** Status polling returns `status: "queued"`

**New fields in response:**
```typescript
interface StatusResponse {
  job_id: string;
  status: "queued" | "processing" | "splitting" | "adding_watermarks" | "finished" | "error";
  progress: number;
  message: string;
  
  // NEW FIELDS (only when status === "queued"):
  queue_position?: number;           // Position in queue (1, 2, 3...)
  jobs_ahead?: number;               // Number of jobs ahead (0, 1, 2...)
  estimated_wait_seconds?: number;   // Seconds until processing starts
  estimated_start_time?: string;     // ISO timestamp when job will start
}
```

**Frontend code:**
```javascript
function pollStatus(jobId) {
  const interval = setInterval(async () => {
    const response = await fetch(`/api/status/${jobId}`);
    const data = await response.json();
    
    if (data.status === 'queued') {
      // Show queue position
      const position = data.queue_position;
      const ahead = data.jobs_ahead;
      const waitMinutes = Math.ceil(data.estimated_wait_seconds / 60);
      
      showMessage(`Queue position: ${position}`);
      showDetails(`${ahead} job(s) ahead. Estimated wait: ${waitMinutes} minute(s)`);
      
      // Keep polling every 1-2 seconds
    }
    else if (data.status === 'processing' || data.status === 'splitting' || data.status === 'adding_watermarks') {
      // Show processing status
      showMessage(`Processing: ${data.message}`);
      showProgress(data.progress);
    }
    else if (data.status === 'finished') {
      // Ready to download
      clearInterval(interval);
      enableDownloadButton();
      
      // IMPORTANT: Warn user about 1-minute window
      showWarning('Download ready! You have 1 minute to download before file is deleted.');
    }
    else if (data.status === 'error') {
      clearInterval(interval);
      showError(`Error: ${data.error || data.message}`);
    }
  }, 1000); // Poll every 1 second
}
```

---

### 4. Warn About 1-Minute Download Window

**When:** Job status becomes `"finished"`

**Important:** Files are deleted either:
- Immediately after first download (200 OK response), OR
- 1 minute after job finishes (if never downloaded)

**Frontend code:**
```javascript
if (data.status === 'finished') {
  // Show prominent warning
  showAlert({
    type: 'warning',
    title: 'Download Ready',
    message: 'Your file is ready! Download within 1 minute or it will be deleted.',
    button: 'Download Now'
  });
  
  enableDownloadButton();
}
```

---

### 5. Handle Download Errors

**New behavior:** If download fails, file may already be deleted.

**Frontend code:**
```javascript
async function downloadFile(jobId) {
  try {
    const response = await fetch(`/api/download/${jobId}`);
    
    if (response.status === 410) {
      // Download window expired
      const data = await response.json();
      showError('Download window expired (1 minute limit). Please upload and process your file again.');
      return;
    }
    
    if (!response.ok) {
      throw new Error('Download failed');
    }
    
    // Download successful
    const blob = await response.blob();
    
    // Verify not empty
    if (blob.size < 1000) {
      throw new Error('Downloaded file is corrupted');
    }
    
    // Save to user's computer
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `watermarked_${jobId}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
    
    showSuccess('Download complete!');
    
    // Note: File is already deleted from server
    
  } catch (error) {
    showError('Download failed. File may have been deleted. Please resubmit your PDF.');
  }
}
```

---

### 6. Prevent Multiple Uploads Per User

**Backend enforces:** One PDF per user at a time (tracked by session cookie)

**If user tries to upload while already processing:**
```javascript
if (response.status === 503) {
  const data = await response.json();
  if (data.message.includes('already have a job')) {
    showError('You already have a file being processed. Please wait for it to complete.');
  }
}
```

**Frontend should:**
- Disable upload button while job is active
- Show current job status prominently
- Only re-enable upload after download or error

---

## Complete Status Flow

```
1. User uploads → Backend queues job
2. Poll /api/status/{job_id} every 1 second:

   Status: "queued"
   - Show: "Position 3, 2 jobs ahead, ~4 minutes wait"
   
   Status: "processing" / "splitting" / "adding_watermarks"
   - Show: Progress bar, "Processing: Adding watermarks (65%)"
   
   Status: "finished"
   - Show: "Download ready! 1 minute window" + Download button
   - Start countdown timer (60 seconds)
   
   Status: "error"
   - Show: Error message
   - Allow new upload

3. User clicks download → File sent + deleted immediately
4. If 1 minute passes → File deleted automatically
```

---

## Example: Complete Upload/Download Flow

```javascript
// Upload
async function handleUpload(file) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('chunk_size', 10);
  
  const response = await fetch('/api/upload', {
    method: 'POST',
    body: formData,
    credentials: 'include' // Important: Send cookies
  });
  
  if (response.status === 503) {
    const data = await response.json();
    alert(`Server busy: ${data.message}`);
    return;
  }
  
  const data = await response.json();
  startPolling(data.job_id);
}

// Polling
function startPolling(jobId) {
  const interval = setInterval(async () => {
    const response = await fetch(`/api/status/${jobId}`);
    const data = await response.json();
    
    updateUI(data);
    
    if (data.status === 'finished' || data.status === 'error') {
      clearInterval(interval);
    }
  }, 1000);
}

// UI Update
function updateUI(data) {
  if (data.status === 'queued') {
    setStatus(`Queue position: ${data.queue_position}`);
    setDetails(`${data.jobs_ahead} ahead, ~${Math.ceil(data.estimated_wait_seconds / 60)} min`);
  }
  else if (data.status === 'finished') {
    setStatus('Ready to download!');
    setWarning('Download within 1 minute');
    enableDownload(data.job_id);
  }
  else if (data.status === 'processing') {
    setStatus(data.message);
    setProgress(data.progress);
  }
  else if (data.status === 'error') {
    setError(data.error || data.message);
  }
}

// Download
async function downloadFile(jobId) {
  try {
    const response = await fetch(`/api/download/${jobId}`);
    
    if (!response.ok) {
      if (response.status === 410) {
        alert('Download expired. Please resubmit.');
      }
      return;
    }
    
    const blob = await response.blob();
    saveAs(blob, 'watermarked.pdf');
    
    showSuccess('Downloaded! File deleted from server.');
    
  } catch (error) {
    alert('Download failed. Please resubmit your file.');
  }
}
```

---

## Quick Checklist

- [ ] Handle 503 response on upload (show retry message)
- [ ] Show queue position when `status === "queued"`
- [ ] Display 1-minute warning when `status === "finished"`
- [ ] Handle 410 response on download (window expired)
- [ ] Disable upload button while job active
- [ ] Include `credentials: 'include'` in fetch requests (for cookies)
- [ ] Poll every 1 second (not faster, not slower)
- [ ] Show clear error if download fails after 1 minute

---

## API Changes Summary

| Endpoint | Change | Impact |
|----------|--------|--------|
| `POST /api/upload` | Can return `503` | Handle server busy |
| `GET /api/status/{id}` | New status `"queued"` + queue fields | Show position/wait time |
| `GET /api/download/{id}` | Deletes file after serving | One-shot download |
| All endpoints | Uses session cookies | Include `credentials: 'include'` |

---

## Testing Checklist

1. ✅ Upload small file → should process immediately
2. ✅ Upload 3 files quickly → 1st processes, 2nd-3rd queued
3. ✅ Try 4th upload → should get 503 rejection
4. ✅ Wait for 1st to finish → download within 1 min
5. ✅ Wait > 1 min after finish → download should fail (410)
6. ✅ Try uploading while job active → should reject
7. ✅ Check queue position updates every second

---

**That's it!** The backend handles all the queue logic. Frontend just needs to:
1. Handle 503 rejection
2. Show queue status
3. Warn about 1-minute window
4. Handle expired downloads
