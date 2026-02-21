# Answers to Frontend & User Questions

## 📋 Frontend Developer Questions

### Q1: Does the backend return a 'merging' status?

**Answer: YES**, the backend returns `status: "merging"` as a **separate status** (not part of 'adding_watermarks').

**Backend code:**
```python
# In modules/processor.py
if status_callback:
    status_callback("merging", progress=80)  # ← Separate "merging" status

merge_chunks(chunk_paths, output_path, status_callback=status_callback)
```

---

### Q2: Should frontend display a new "Merging chunks" step?

**Answer: YES**, display **4 processing steps** (not 3):

```javascript
const PROCESSING_STEPS = {
  'splitting': {
    label: 'Step 1: Splitting PDF',
    progressRange: '1-30%',
    icon: '✂️'
  },
  'adding_watermarks': {
    label: 'Step 2: Adding Watermarks',
    progressRange: '31-79%',
    icon: '🎨'
  },
  'merging': {  // ← NEW STEP
    label: 'Step 3: Merging Chunks',
    progressRange: '80-100%',
    icon: '🔄'
  },
  'finished': {
    label: 'Complete',
    progressRange: '100%',
    icon: '✅'
  }
};
```

**Why:** The merge phase can take several minutes for large PDFs with many chunks. Users deserve to see this progress.

---

### Q3: What's the backend status response field for merge phase?

**Answer:** The response structure is:

```json
{
  "job_id": "abc123",
  "status": "merging",        ← String: "merging" (not "adding_watermarks")
  "progress": 85,             ← Number: 80-100 during merge phase
  "message": "Merging chunks back into final PDF"
}
```

**NOT:**
```json
{
  "status": "adding_watermarks",  ← ❌ Wrong - it changes to "merging"
  "merge_progress": 85             ← ❌ Wrong - uses same "progress" field
}
```

**Example status progression:**
```javascript
// Request 1:
{ "status": "adding_watermarks", "progress": 65 }

// Request 2:
{ "status": "adding_watermarks", "progress": 79 }

// Request 3: ← Status changes here
{ "status": "merging", "progress": 80 }

// Request 4:
{ "status": "merging", "progress": 85 }

// Request 5:
{ "status": "merging", "progress": 95 }

// Request 6:
{ "status": "finished", "progress": 100 }
```

---

### Q4: Any other API response changes?

**Answer: NO**, the API structure remains the same as documented in the guide:

```typescript
interface StatusResponse {
  job_id: string;
  status: 'queued' | 'processing' | 'splitting' | 'adding_watermarks' | 'merging' | 'finished' | 'error';
  progress: number;  // 0-100
  message: string;
  
  // Conditional fields (only present for specific statuses)
  queue_position?: number;
  jobs_ahead?: number;
  estimated_wait_seconds?: number;
  estimated_start_time?: string;
  result_path?: string;
  error?: string;
}
```

**Key points:**
- ✅ All status values use the same `progress` field (0-100)
- ✅ `message` field always contains human-readable text
- ✅ No new fields added for merge phase
- ✅ Same polling interval: **1 second**

---

## 📤 User Question: Why No Percentage for Uploading?

### Short Answer:
Upload happens **synchronously** during the POST request. There's no backend progress because the file must be **completely uploaded** before the backend can return a `job_id`.

### Detailed Explanation:

#### Current Flow:
```
┌─────────────────────────────────────────┐
│ 1. User clicks "Upload"                 │
│    Frontend sends entire file to backend│
│    ⏳ Upload happens here (no backend   │
│       tracking possible yet)            │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│ 2. Backend receives complete file       │
│    - Validates file                     │
│    - Checks queue capacity              │
│    - Creates job_id                     │
│    - Returns response                   │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│ 3. Frontend receives job_id             │
│    NOW progress tracking starts at 0%   │
│    Poll /api/status/{job_id}            │
└─────────────────────────────────────────┘
```

#### Why This Happens:

1. **HTTP Request-Response Model**: The browser uploads the entire file in one HTTP request before the server can respond

2. **Backend Can't Track Upload Progress**: The backend only sees the request once the file is fully uploaded

3. **Progress Tracking Starts After Upload**: The `job_id` is created only after the file is saved to disk

#### Solution: Client-Side Upload Progress

If you want upload progress, implement it **on the frontend** using `XMLHttpRequest` or `fetch` with progress events:

```javascript
async function uploadWithProgress(file, chunkSize, onProgress) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('chunk_size', chunkSize);
    
    const xhr = new XMLHttpRequest();
    
    // Track upload progress (client-side)
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const percentComplete = (e.loaded / e.total) * 100;
        onProgress(percentComplete);  // Update UI: 0-100%
      }
    });
    
    xhr.addEventListener('load', () => {
      if (xhr.status === 200) {
        const data = JSON.parse(xhr.responseText);
        resolve(data.job_id);
      } else {
        reject(new Error('Upload failed'));
      }
    });
    
    xhr.addEventListener('error', () => {
      reject(new Error('Network error'));
    });
    
    xhr.open('POST', '/api/upload');
    xhr.setRequestHeader('credentials', 'include');
    xhr.send(formData);
  });
}

// Usage:
uploadWithProgress(file, 10, (uploadPercent) => {
  // Show: "Uploading... 45%"
  showUploadProgress(uploadPercent);
})
.then(jobId => {
  // Now start backend progress polling
  showMessage('Upload complete! Processing queued...');
  startStatusPolling(jobId);
});
```

#### Recommended UI Flow with Upload Progress:

```
Stage 1: UPLOADING (Client-Side Progress)
┌──────────────────────────────────────┐
│ 📤 Uploading file...                │
│ [████████░░░░░░░░░░] 45%            │
│ 234 MB / 520 MB                     │
└──────────────────────────────────────┘

Stage 2: QUEUED (Backend Progress)
┌──────────────────────────────────────┐
│ ⏳ Queued                            │
│ Position: 2 (1 job ahead)           │
│ Estimated wait: 3 minutes           │
└──────────────────────────────────────┘

Stage 3: PROCESSING (Backend Progress)
┌──────────────────────────────────────┐
│ ⚙️ Processing                        │
│ [████████████░░░░░] 65%             │
│ Adding watermarks...                │
└──────────────────────────────────────┘

Stage 4: MERGING (Backend Progress)
┌──────────────────────────────────────┐
│ 🔄 Merging chunks                   │
│ [████████████████░░] 85%            │
│ Combining processed chunks...       │
└──────────────────────────────────────┘

Stage 5: FINISHED
┌──────────────────────────────────────┐
│ ✅ Ready to download!               │
│ ⚠️  Download within 1 minute        │
│ [Download Now] 🕐 58s remaining     │
└──────────────────────────────────────┘
```

---

## 🎯 Summary for Frontend Implementation

### What to Display:

1. **Upload Phase (Client-Side)**
   - Show: "Uploading... X%"
   - Progress: 0-100% (calculated from bytes sent)
   - Duration: Depends on file size + network speed

2. **Queued Phase (Backend)**
   - Show: "Queue Position: X, Y jobs ahead"
   - Progress: 0%
   - Duration: Varies based on queue

3. **Processing Phases (Backend)**
   - **Splitting**: 1-30% progress
   - **Adding Watermarks**: 31-79% progress
   - **Merging**: 80-100% progress  ← **NEW: Separate step**

4. **Finished Phase**
   - Show: Download button + 1-minute countdown
   - Progress: 100%

---

## 🔧 Sample Implementation with Upload Progress

```javascript
class PDFWatermarkApp {
  async handleFileUpload(file, chunkSize) {
    // Stage 1: Show upload progress (client-side)
    showStage('uploading');
    
    const jobId = await this.uploadWithProgress(file, chunkSize, (percent) => {
      updateProgress(percent, 'Uploading file...');
    });
    
    // Stage 2: Backend processing
    showStage('processing');
    await this.pollBackendProgress(jobId);
  }
  
  uploadWithProgress(file, chunkSize, onProgress) {
    return new Promise((resolve, reject) => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('chunk_size', chunkSize);
      
      const xhr = new XMLHttpRequest();
      
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          const percent = (e.loaded / e.total) * 100;
          onProgress(Math.round(percent));
        }
      };
      
      xhr.onload = () => {
        if (xhr.status === 200) {
          const data = JSON.parse(xhr.responseText);
          resolve(data.job_id);
        } else if (xhr.status === 503) {
          const data = JSON.parse(xhr.responseText);
          reject(new Error(data.message));
        } else {
          reject(new Error('Upload failed'));
        }
      };
      
      xhr.onerror = () => reject(new Error('Network error'));
      
      xhr.open('POST', '/api/upload');
      xhr.withCredentials = true;  // For cookies
      xhr.send(formData);
    });
  }
  
  async pollBackendProgress(jobId) {
    const interval = setInterval(async () => {
      const response = await fetch(`/api/status/${jobId}`);
      const data = await response.json();
      
      // Update UI based on status
      const stepLabels = {
        'queued': '⏳ Queued',
        'splitting': '✂️ Splitting PDF',
        'adding_watermarks': '🎨 Adding Watermarks',
        'merging': '🔄 Merging Chunks',  // ← New step
        'finished': '✅ Complete'
      };
      
      updateProgress(data.progress, stepLabels[data.status] || data.message);
      
      if (data.status === 'finished') {
        clearInterval(interval);
        showDownloadButton(jobId);
      } else if (data.status === 'error') {
        clearInterval(interval);
        showError(data.error);
      }
    }, 1000);
  }
}
```

---

## ✅ Final Checklist for Frontend

- [ ] Display **4 processing steps** (splitting, watermarks, merging, finished)
- [ ] Watch for `status: "merging"` (separate from "adding_watermarks")
- [ ] Show merge progress: 80% → 85% → 90% → 95% → 100%
- [ ] (Optional) Implement client-side upload progress using XMLHttpRequest
- [ ] Poll every 1 second during backend processing
- [ ] Show 1-minute countdown timer after status becomes "finished"

---

**Questions answered?** Let me know if you need clarification on any points!
