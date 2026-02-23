# Frontend Integration Guide - Enhanced Pre-Upload Queue Check

## 🎯 Overview

The backend now checks **queue capacity BEFORE upload starts** to prevent wasted bandwidth and provide better UX. This guide explains the required frontend changes.

---

## 📋 What Changed in Backend

### Key Improvements:
1. ✅ `/api/check-size` now checks **file size + queue capacity + active jobs**
2. ✅ Uses **4x RAM and 2x disk multipliers** for safe concurrent processing
3. ✅ Returns detailed queue status (active jobs, queue count, retry time)
4. ✅ Prevents upload if queue is full (saves bandwidth!)
5. ✅ Maintains FIFO queue order with opportunistic concurrency

### Benefits:
- **No wasted uploads**: Users know queue is full in < 1 second (not after 10-20 sec upload)
- **Better feedback**: Shows "2 jobs processing" before upload starts
- **Faster throughput**: Multiple small files can process concurrently
- **Safe from OOM**: 3-4x resource buffer prevents server crashes

---

## 🔄 New Flow Diagram

### Before (Old):
```
User selects file
    ↓
Upload starts → 0%...50%...100% (10-20 seconds)
    ↓
Backend checks queue
    ↓
If full: "Queue full!" ❌ (bandwidth wasted!)
If OK: "Queued" ✅
```

### After (New):
```
User selects file
    ↓
Check queue first → /api/check-size (< 1 second)
    ↓
If full: "Queue full (2 jobs active). Retry in 3 min" ❌ (NO upload!)
If OK: Upload starts → 0%...100% (10-20 seconds) ✅
    ↓
"Queued for processing!"
```

---

## 📡 Updated API Response

### `/api/check-size` - Enhanced Response

**Request:**
```typescript
POST /api/check-size
Content-Type: application/json

{
  "file_size": 30000000  // File size in bytes
}
```

**Response - Success (Queue Available):**
```typescript
{
  "allowed": true,                    // Both size AND queue OK
  "max_allowed_size": 5242880,        // 5MB limit
  "available_ram": 450000000,         // Current available RAM
  "message": "OK",                    // Human-readable message
  "queue_available": true,            // ⭐ Can accept this job now
  "queue_message": "OK",              // Queue-specific message
  "retry_after_seconds": null,        // No wait needed
  "queue_count": 2,                   // ⭐ 2 jobs in queue
  "active_jobs": 1                    // ⭐ 1 job currently processing
}
```

**Response - Queue Full:**
```typescript
{
  "allowed": false,
  "max_allowed_size": 5242880,
  "available_ram": 150000000,
  "message": "Server memory insufficient. Please try again shortly.",
  "queue_available": false,           // ⭐ Queue cannot accept
  "queue_message": "Server memory insufficient. Please try again shortly.",
  "retry_after_seconds": 180,         // ⭐ Retry after 3 minutes
  "queue_count": 5,                   // 5 jobs in queue
  "active_jobs": 3                    // 3 jobs processing
}
```

**Response - File Too Large:**
```typescript
{
  "allowed": false,
  "max_allowed_size": 5242880,
  "available_ram": 450000000,
  "message": "File too large (8.2MB). Maximum allowed: 5MB",
  "queue_available": true,            // Queue has space, but file too big
  "queue_message": "OK",
  "retry_after_seconds": null,        // No point waiting, file is too large
  "queue_count": 2,
  "active_jobs": 1
}
```

---

## 💻 Required Frontend Changes

### 1. Update Response Interface

```typescript
// Update your existing interface
interface CheckSizeResponse {
  allowed: boolean;
  max_allowed_size: number;
  available_ram: number;
  message: string;
  // NEW FIELDS:
  queue_available: boolean;     // Can queue accept this job?
  queue_message: string;         // Queue-specific message
  retry_after_seconds: number | null;  // Wait time if queue full
  queue_count: number;           // Jobs in queue
  active_jobs: number;           // Jobs processing
}
```

### 2. Update Upload Flow

**Complete Implementation:**

```javascript
// Main upload handler
async function handleFileUpload(file) {
  try {
    // Step 1: Check queue BEFORE uploading
    const canProceed = await checkQueueBeforeUpload(file);
    
    if (!canProceed) {
      return;  // Stop here, user already informed
    }
    
    // Step 2: Queue has space, NOW start upload
    await uploadFile(file);
    
  } catch (error) {
    showError('Upload failed: ' + error.message);
  }
}

// Check queue capacity before upload
async function checkQueueBeforeUpload(file) {
  showStatus('Checking server availability...');
  
  try {
    const response = await fetch('http://localhost:8000/api/check-size', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        file_size: file.size
      }),
      credentials: 'include'  // IMPORTANT: Send session cookie
    });
    
    const result = await response.json();
    
    // Case 1: Both size and queue OK → proceed with upload
    if (result.allowed && result.queue_available) {
      const statusMsg = result.active_jobs > 0
        ? `Ready! ${result.active_jobs} job(s) processing. Uploading...`
        : 'Ready! Uploading...';
      showStatus(statusMsg);
      return true;
    }
    
    // Case 2: File too large (permanent rejection)
    if (!result.allowed && result.queue_available) {
      showError(result.message);
      // Example: "File too large (8.2MB). Maximum allowed: 5MB"
      return false;
    }
    
    // Case 3: Queue full (temporary - can retry)
    if (!result.queue_available) {
      const minutes = Math.ceil(result.retry_after_seconds / 60);
      const statusMsg = 
        `Server busy (${result.active_jobs} job(s) processing, ` +
        `${result.queue_count} in queue). ` +
        `Please try again in ${minutes} minute(s).`;
      
      showError(statusMsg);
      // Optional: Enable a "Retry" button
      // enableRetryButton(() => handleFileUpload(file));
      return false;
    }
    
    // Case 4: Unknown state (shouldn't happen)
    showError('Unable to check server status. Please try again.');
    return false;
    
  } catch (error) {
    showError('Network error: ' + error.message);
    return false;
  }
}

// Upload file with progress
async function uploadFile(file) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('chunk_size', 10);
    
    const xhr = new XMLHttpRequest();
    
    // Track upload progress
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const percent = Math.round((e.loaded / e.total) * 100);
        showStatus(`Uploading: ${percent}%`);
      }
    });
    
    xhr.addEventListener('load', () => {
      if (xhr.status === 200) {
        const result = JSON.parse(xhr.responseText);
        showStatus('Upload complete! Processing...');
        startPolling(result.job_id);
        resolve(result.job_id);
      } else if (xhr.status === 503) {
        // Queue filled up during upload (rare)
        const error = JSON.parse(xhr.responseText);
        showError('Server became busy during upload. Please retry.');
        reject(new Error('Queue full'));
      } else {
        showError('Upload failed');
        reject(new Error('Upload failed'));
      }
    });
    
    xhr.addEventListener('error', () => {
      showError('Network error during upload');
      reject(new Error('Network error'));
    });
    
    xhr.open('POST', 'http://localhost:8000/api/upload');
    xhr.withCredentials = true;  // IMPORTANT: Send session cookie
    xhr.send(formData);
  });
}
```

### 3. UI Status Messages

**Recommended status messages:**

```javascript
// During check
"Checking server availability..."

// Queue available
"Ready! Uploading..."
"Ready! 2 job(s) processing. Uploading..."

// Queue full
"Server busy (3 job(s) processing, 5 in queue). Please try again in 3 minute(s)."

// File too large
"File too large (8.2MB). Maximum allowed: 5MB"

// Uploading
"Uploading: 45%"

// Upload complete
"Upload complete! Processing..."
```

---

## 🎨 Optional: Auto-Retry with Countdown

If you want to automatically retry when queue is full:

```javascript
async function handleFileUploadWithRetry(file, maxRetries = 3) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    const check = await checkQueueStatus(file);
    
    if (check.allowed && check.queue_available) {
      // Queue has space - upload now!
      await uploadFile(file);
      return;
    }
    
    if (!check.queue_available && check.retry_after_seconds) {
      // Queue full - wait and retry
      if (attempt < maxRetries) {
        await waitWithCountdown(check.retry_after_seconds, check);
        // Loop continues, will retry
      } else {
        showError('Server still busy after multiple retries. Please try later.');
      }
    } else {
      // Permanent rejection (file too large)
      showError(check.message);
      return;
    }
  }
}

async function waitWithCountdown(seconds, queueInfo) {
  const endTime = Date.now() + (seconds * 1000);
  
  return new Promise((resolve) => {
    const interval = setInterval(() => {
      const remaining = Math.ceil((endTime - Date.now()) / 1000);
      
      if (remaining <= 0) {
        clearInterval(interval);
        showStatus('Rechecking server...');
        resolve();
        return;
      }
      
      const mins = Math.floor(remaining / 60);
      const secs = remaining % 60;
      showStatus(
        `Server busy (${queueInfo.active_jobs} processing, ` +
        `${queueInfo.queue_count} queued). ` +
        `Retrying in ${mins}:${secs.toString().padStart(2, '0')}...`
      );
    }, 1000);
  });
}
```

---

## ⚠️ Important Notes

### 1. Session Cookie Required
Both `/api/check-size` and `/api/upload` require session cookies for user tracking:

```javascript
fetch(url, {
  credentials: 'include'  // ← MUST include this!
})
```

### 2. 503 During Upload (Edge Case)
Even after `/api/check-size` returns OK, the queue might fill up during the upload (if 10-20 seconds pass). Handle 503 response:

```javascript
xhr.addEventListener('load', () => {
  if (xhr.status === 503) {
    // Queue filled up during upload
    showError('Server became busy during upload. Please retry in a few minutes.');
  }
});
```

### 3. Queue Position Updates
The queue position is NOT reserved by `/api/check-size`. It's only assigned when `/api/upload` completes. This is intentional to prevent ghost reservations.

### 4. Concurrent Processing
Multiple users can process simultaneously if resources allow. Users with small files might finish before users who uploaded earlier with large files. This is expected behavior (opportunistic concurrency).

---

## 🧪 Testing Checklist

### Test Cases:

**1. Normal Flow (Queue Available)**
- [ ] Select 30MB file
- [ ] See "Checking server availability..." (< 1 second)
- [ ] See "Ready! Uploading..." → upload starts
- [ ] Upload shows 0-100% progress
- [ ] See "Queued for processing!"

**2. Queue Full**
- [ ] Backend has 2-3 jobs processing
- [ ] Select large file (70MB+)
- [ ] See "Server busy (X jobs processing). Try again in Y minutes"
- [ ] NO upload happens (progress never shows)

**3. File Too Large**
- [ ] Select 6MB file
- [ ] See "File too large (6.0MB). Maximum allowed: 5MB"
- [ ] NO upload happens

**4. Small File Concurrent**
- [ ] Backend has 1 large job processing
- [ ] Select 5MB file
- [ ] Should succeed and process concurrently

**5. Queue Fills During Upload (503)**
- [ ] Start upload when queue has 1 spot left
- [ ] Another user uploads while your upload in progress
- [ ] Your upload completes → should get 503
- [ ] See "Server became busy during upload. Please retry."

---

## 📊 Before/After Comparison

| Scenario | Before (Old) | After (New) |
|----------|--------------|-------------|
| Queue full | Upload 10-20 sec → "Queue full!" | Check < 1 sec → "Queue full!" (no upload) |
| Bandwidth | Wasted 5MB if rejected | Zero waste |
| User feedback | After long upload | Immediate (< 1 sec) |
| Queue visibility | Hidden | Shows active jobs + queue count |
| Retry guidance | Generic "try later" | Specific "retry in 3 minutes" |

---

## 🔗 API Endpoint Reference

### Base URL
```
Local: http://localhost:8000
Production: https://your-render-app.onrender.com
```

### Endpoints

**1. Check Size + Queue (NEW - Call this first!)**
```
POST /api/check-size
Body: { "file_size": 30000000 }
Cookie: session_id (auto-sent)
Returns: SizeCheckResponse (with queue info)
```

**2. Upload File (Call only if check passed)**
```
POST /api/upload
Body: FormData with 'file' and 'chunk_size'
Cookie: session_id (auto-sent)
Returns: { "job_id": "...", "message": "..." }
```

**3. Check Status (Existing - no changes)**
```
GET /api/status/{job_id}
Returns: Progress 0-100%
```

**4. Download Result (Existing - no changes)**
```
GET /api/download/{job_id}
Returns: Watermarked PDF file
```

---

## ✅ Summary

**Required Changes:**
1. ✅ Update response interface with new queue fields
2. ✅ Call `/api/check-size` BEFORE starting upload
3. ✅ Only upload if `allowed && queue_available`
4. ✅ Show queue status (active jobs, wait time)
5. ✅ Handle 503 during upload (edge case)

**Testing:**
- Test with queue available
- Test with queue full
- Test with file too large
- Test concurrent small files

**No Changes Needed:**
- Status polling (`/api/status/{job_id}`)
- Download endpoint (`/api/download/{job_id}`)
- Progress display (still 0-100%)

---

## 🤝 Questions?

Backend automatically handles:
- ✅ FIFO queue order (oldest first)
- ✅ Concurrent processing (when resources allow)
- ✅ 3-4x resource safety buffer
- ✅ Session tracking (multiple jobs per user allowed)
- ✅ Automatic cleanup after 1 hour

Frontend just needs to:
1. Check queue before upload
2. Show appropriate messages
3. Handle responses correctly

Good luck! 🚀
