# Frontend Q&A - Queue System Clarifications

## 🎯 Quick Summary

**Key Point:** `/api/check-size` does NOT reserve queue positions or assign job IDs. It only checks current capacity. Queue position is assigned ONLY after `/api/upload` completes.

---

## ❓ Question 1: Queue Position Without Upload

**Frontend asked:**
> "How can backend assign a queue position (#1, #2, etc.) if the file hasn't been uploaded yet?"

**Answer: Option A is correct** ✅

- `/api/check-size` returns **GENERAL queue status** (how many jobs exist)
- It does **NOT** assign a specific position to this user
- No "reservation" or "slot holding" happens during check-size
- Queue position is assigned **ONLY when `/api/upload` completes** (when job is created)

**Response fields from `/api/check-size`:**
```typescript
{
  queue_available: boolean,    // Can queue accept A job right now?
  queue_count: number,          // Total jobs currently queued
  active_jobs: number,          // Jobs currently processing
  retry_after_seconds: number?, // How long to wait if full
  // NO position field!
  // NO session reservation!
}
```

**Why no reservation?**
- Prevents "ghost reservations" from users who check but never upload
- Keeps queue honest (only actual uploads get spots)
- Simpler implementation

---

## ❓ Question 2: "Backend gives us signal"

**Frontend asked:**
> "How does 'backend gives us signal' work? WebSocket? SSE? Polling?"

**Answer: Simple polling of `/api/check-size`** ✅

**Implementation:**
```javascript
async function waitForQueueSpace(file) {
  while (true) {
    // Poll check-size every 10-30 seconds
    const check = await fetch('/api/check-size', {
      method: 'POST',
      body: JSON.stringify({ file_size: file.size }),
      credentials: 'include'
    });
    
    const result = await check.json();
    
    if (result.queue_available) {
      // Space available! Start upload now
      return true;
    }
    
    // Still full, wait and retry
    const waitSeconds = result.retry_after_seconds || 30;
    await sleep(waitSeconds * 1000);
    // Loop continues...
  }
}
```

**No WebSocket. No SSE. Just HTTP polling.**

**Polling frequency recommendation:**
- If `retry_after_seconds` provided: Use that value
- Otherwise: Poll every 30 seconds
- Don't poll too fast (< 10 sec) - wastes resources

---

## ❓ Question 3: Two "Not OK" States (< 10 vs >= 10)

**Frontend asked:**
> "queue_count < 10: wait and poll, queue_count >= 10: show 503?"

**Answer: There's NO special < 10 vs >= 10 logic in backend** ❌

**What backend actually does:**
```python
# Backend logic (simplified)
if queue_full:
    return {
        "queue_available": false,
        "retry_after_seconds": 180,  # Example: 3 minutes
        "queue_count": 5,  # Could be any number
        ...
    }
    # Always returns HTTP 200, never 503 from check-size
```

**Frontend decides the UX:**

```javascript
// Frontend can choose how to handle based on queue_count
const check = await checkSize(file);

if (!check.queue_available) {
  if (check.queue_count >= 10) {
    // Too many jobs - tell user to come back later
    showError(`Server very busy (${check.queue_count} jobs). Please try again in ${check.retry_after_seconds / 60} minutes.`);
  } else {
    // Not too many - offer to wait
    showMessage(`Queue busy (${check.queue_count} jobs). Waiting...`);
    await waitForSpace(file);  // Polls check-size repeatedly
  }
}
```

**Important:**
- `/api/check-size` always returns **HTTP 200** (never 503)
- The `queue_available: false` field indicates queue is full
- Frontend chooses whether to wait or give up based on `queue_count`

---

## ❓ Question 4: Current vs Enhanced Flow

**Let me diagram the ACTUAL flow:**

### ✅ Correct Enhanced Flow (What Backend Actually Does):

```
User clicks "Process"
    ↓
Frontend calls /api/check-size (< 1 sec)
    ↓
Backend checks: Can I fit this job with 3-4x safety buffer?
    ↓
    ├─ If queue_available: true
    │      ↓
    │  Frontend starts upload immediately
    │      ↓
    │  /api/upload receives file (10-20 sec)
    │      ↓
    │  Backend RE-CHECKS capacity (gap protection)
    │      ↓
    │      ├─ Still OK: Create job with position, status='queued'
    │      └─ Now full: Return 503 (race condition)
    │
    └─ If queue_available: false
           ↓
       Frontend shows: "Queue full (X jobs). Retry in Y min"
           ↓
       OPTION A: User manually retries later
       OPTION B: Frontend polls check-size until space available
```

**Key Points:**
1. **No position assigned during check-size** - only checks capacity
2. **Position assigned AFTER upload completes** - when job is created
3. **No "waiting in queue without upload"** - must upload to get position
4. **Race condition handled** - upload re-checks capacity

**Wrong understanding to clarify:**
- ❌ "Check-size assigns position" - NO
- ❌ "Backend holds a spot during wait" - NO
- ❌ "Position exists before upload" - NO
- ✅ "Check-size only says 'space available or not'" - YES

---

## ❓ Question 5: Race Condition

**Frontend asked:**
> "Check says OK, user uploads (10 sec), during upload queue fills. What happens?"

**Answer: Upload endpoint re-checks and may reject with 503** ✅

**Implementation:**

```python
# /api/upload endpoint (app.py line 373)
@app.post("/api/upload")
async def upload_pdf(file):
    # File upload completes (10-20 seconds elapsed)
    content = await file.read()
    file_size = len(content)
    
    # RE-CHECK capacity (queue might have filled during upload)
    can_accept, message, retry_info = queue_manager.can_accept_job(session, file_size)
    
    if not can_accept:
        # Queue filled up during upload - reject!
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Server at capacity",
                "message": message,
                "retry_after_seconds": retry_info['retry_after_seconds']
            }
        )
    
    # Still OK - create job and assign position
    queue_manager.add_job(job_id, session, file_path, file_size, chunk_size)
    return {"job_id": job_id, "message": "Queued"}
```

**Frontend handling:**

```javascript
xhr.addEventListener('load', () => {
  if (xhr.status === 200) {
    // Success! Job created and queued
    const result = JSON.parse(xhr.responseText);
    startPolling(result.job_id);
  } else if (xhr.status === 503) {
    // Queue filled during upload (race condition)
    const error = JSON.parse(xhr.responseText);
    showError(
      'Server became busy during upload. ' +
      `Please retry in ${error.retry_after_seconds / 60} minutes.`
    );
  }
});
```

**Trade-off:**
- ❌ Small chance of wasted upload (if queue fills during 10-20 sec upload)
- ✅ No complex reservation system needed
- ✅ Prevents ghost reservations
- ✅ Simpler and more reliable

**How often does this happen?**
- Rare! Only if queue fills in the 10-20 sec upload window
- With 3-4x safety buffer, queue fills slowly
- Most uploads succeed

---

## 📋 Complete API Schemas

### 1. `/api/check-size` - Check Queue Capacity

**Request:**
```typescript
POST /api/check-size
Content-Type: application/json
Cookie: session_id (auto-sent)

{
  "file_size": 30000000  // bytes
}
```

**Response (Always HTTP 200):**
```typescript
{
  // File size check
  "allowed": boolean,              // Both size AND queue OK
  "max_allowed_size": number,      // 85MB = 89128960 bytes
  "available_ram": number,         // Current available RAM
  "message": string,               // Human-readable message
  
  // Queue capacity check (NEW)
  "queue_available": boolean,      // Can accept job right now (with 3-4x buffer)?
  "queue_message": string,         // Queue-specific message
  "retry_after_seconds": number?, // How long to wait if full (null if available)
  "queue_count": number,           // Current jobs in queue (NOT your position!)
  "active_jobs": number            // Jobs currently processing
}
```

**Example responses:**

**Success (Queue Available):**
```json
{
  "allowed": true,
  "max_allowed_size": 89128960,
  "available_ram": 450000000,
  "message": "OK",
  "queue_available": true,
  "queue_message": "OK",
  "retry_after_seconds": null,
  "queue_count": 2,
  "active_jobs": 1
}
```
→ Frontend action: Start upload immediately

**Queue Full:**
```json
{
  "allowed": false,
  "max_allowed_size": 89128960,
  "available_ram": 150000000,
  "message": "Server memory insufficient. Please try again shortly.",
  "queue_available": false,
  "queue_message": "Server memory insufficient. Please try again shortly.",
  "retry_after_seconds": 180,
  "queue_count": 5,
  "active_jobs": 3
}
```
→ Frontend action: Wait or show retry message

**File Too Large:**
```json
{
  "allowed": false,
  "max_allowed_size": 89128960,
  "available_ram": 450000000,
  "message": "File too large (103MB). Maximum allowed: 85MB",
  "queue_available": true,
  "queue_message": "OK",
  "retry_after_seconds": null,
  "queue_count": 2,
  "active_jobs": 1
}
```
→ Frontend action: Show error, don't allow upload

### 2. `/api/upload` - Upload File (After Check Passes)

**Request:**
```
POST /api/upload
Content-Type: multipart/form-data
Cookie: session_id (auto-sent)

FormData:
  - file: (binary PDF)
  - chunk_size: 10 (integer)
```

**Response - Success (HTTP 200):**
```json
{
  "job_id": "abc-123-def-456",
  "message": "File uploaded successfully and queued for processing"
}
```
→ Frontend action: Start polling `/api/status/{job_id}`

**Response - Queue Filled During Upload (HTTP 503):**
```json
{
  "detail": {
    "error": "Server at capacity",
    "message": "Server memory insufficient. Please try again in 3 minutes.",
    "retry_after_seconds": 180,
    "retry_after_time": "2026-02-21T10:15:00.000Z",
    "reason": "memory"
  }
}
```
→ Frontend action: Show retry message

### 3. `/api/status/{job_id}` - Check Job Progress

**No changes - same as before.**

---

## 🔄 Recommended Implementation Flow

### Option A: Simple (No Automatic Waiting)

```javascript
async function handleUpload(file) {
  // 1. Check queue
  const check = await fetch('/api/check-size', {
    method: 'POST',
    body: JSON.stringify({ file_size: file.size }),
    credentials: 'include'
  }).then(r => r.json());
  
  // 2. Handle based on response
  if (!check.allowed) {
    showError(check.message);
    return;
  }
  
  if (!check.queue_available) {
    // Queue full - let user decide
    const minutes = Math.ceil(check.retry_after_seconds / 60);
    showError(
      `Server busy (${check.active_jobs} processing, ${check.queue_count} queued). ` +
      `Please retry in ${minutes} minutes.`
    );
    return;
  }
  
  // 3. Queue available - upload!
  showStatus('Uploading...');
  await uploadFile(file);
}
```

### Option B: Auto-Wait for Queue Space (Recommended)

```javascript
async function handleUpload(file) {
  // 1. Check queue and wait if needed
  while (true) {
    const check = await fetch('/api/check-size', {
      method: 'POST',
      body: JSON.stringify({ file_size: file.size }),
      credentials: 'include'
    }).then(r => r.json());
    
    // File too large - permanent rejection
    if (!check.allowed && check.queue_available) {
      showError(check.message);
      return;
    }
    
    // Queue has space - proceed!
    if (check.queue_available) {
      break;
    }
    
    // Queue full - wait and retry
    if (check.queue_count >= 10) {
      // Too many jobs - give up
      showError(`Server very busy (${check.queue_count} jobs). Please try again later.`);
      return;
    }
    
    // Not too many - wait with countdown
    await waitWithCountdown(check.retry_after_seconds, check);
    showStatus('Rechecking server...');
    // Loop continues...
  }
  
  // 2. Upload!
  showStatus('Uploading...');
  await uploadFile(file);
}

async function waitWithCountdown(seconds, queueInfo) {
  const endTime = Date.now() + (seconds * 1000);
  
  return new Promise((resolve) => {
    const interval = setInterval(() => {
      const remaining = Math.ceil((endTime - Date.now()) / 1000);
      
      if (remaining <= 0) {
        clearInterval(interval);
        resolve();
        return;
      }
      
      const mins = Math.floor(remaining / 60);
      const secs = remaining % 60;
      showStatus(
        `Queue busy (${queueInfo.active_jobs} processing, ${queueInfo.queue_count} queued). ` +
        `Retrying in ${mins}:${secs.toString().padStart(2, '0')}...`
      );
    }, 1000);
  });
}
```

---

## 🎯 Key Takeaways

1. **No Position Before Upload** ❌
   - `/api/check-size` does NOT assign queue positions
   - Position only exists AFTER upload completes

2. **Polling for Space** ✅
   - Poll `/api/check-size` repeatedly until `queue_available: true`
   - Use `retry_after_seconds` for polling interval
   - No WebSocket/SSE

3. **Always HTTP 200** ✅
   - `/api/check-size` never returns 503
   - Use `queue_available` flag to determine if queue is full

4. **Race Condition Handled** ✅
   - `/api/upload` re-checks capacity
   - May return 503 if queue filled during upload
   - Frontend should handle this gracefully

5. **Frontend Decides UX** ✅
   - Backend provides `queue_count` and `retry_after_seconds`
   - Frontend chooses: wait automatically, or ask user to retry
   - No hard rule about "< 10 jobs" vs ">= 10 jobs"

---

## 📚 Related Documents

1. **[FRONTEND_ENHANCED_CHECK_SIZE_GUIDE.md](FRONTEND_ENHANCED_CHECK_SIZE_GUIDE.md)** - Complete implementation guide with code examples
2. **Current document** - Q&A addressing specific questions

---

## ❓ Still Have Questions?

**Common follow-ups:**

**Q: Can we reserve a position during check-size?**
A: No. This would require complex session management and timeout logic. Current approach is simpler and more reliable.

**Q: Why not WebSocket for "space available" notifications?**
A: Adds complexity. Simple HTTP polling is sufficient and more reliable.

**Q: What if many users are waiting and all try to upload when space opens?**
A: First upload to complete wins the spot. Others get 503 and retry. This is fair (first-come-first-served).

**Q: Should we cache check-size results?**
A: No. Always re-check to get current queue state. Queue can change rapidly.

**Q: Can one user have multiple uploads waiting?**
A: Yes! Users can upload multiple files concurrently. Each upload is treated independently and queued based on available resources.

---

## ✅ Summary

**What `/api/check-size` does:**
- ✅ Checks if queue can accept A job right now
- ✅ Returns current queue statistics
- ✅ Provides retry guidance
- ❌ Does NOT assign positions
- ❌ Does NOT reserve spots
- ❌ Does NOT create jobs

**What `/api/upload` does:**
- ✅ Receives uploaded file
- ✅ Re-checks queue capacity
- ✅ Creates job and assigns position
- ✅ Returns 503 if queue filled during upload

**Frontend responsibility:**
- Check queue before upload
- Wait/poll if queue full (optional)
- Handle 503 from upload endpoint
- Show appropriate status messages

Good luck with implementation! 🚀
