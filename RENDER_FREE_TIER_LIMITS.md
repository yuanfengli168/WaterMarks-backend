# Render Free Tier - Safe File Size Limits

## 🚨 Critical: Your Server Just Crashed

Your backend restarted mid-processing because it **ran out of memory**. Here's what happened:

1. ❌ File was too large for 512MB RAM
2. ❌ Server crashed during processing
3. ❌ Job data was lost (in-memory storage)
4. ❌ Frontend got 502 Bad Gateway errors

## Memory Usage During Processing

Processing a PDF uses **3-4x the file size** in RAM:

| File Size | RAM Used During Processing | Safe on Free Tier? |
|-----------|----------------------------|-------------------|
| 10MB      | ~40MB                      | ✅ Always safe     |
| 25MB      | ~100MB                     | ✅ Safe           |
| 50MB      | ~200MB                     | ⚠️ Risky          |
| 75MB      | ~300MB                     | ❌ Will crash     |
| 100MB     | ~400MB                     | ❌ Will crash     |

**Why?** During processing, the backend holds in memory:
- Original PDF file
- Split chunks (multiple files)
- Watermarked chunks (multiple files)
- Final merged PDF
- Python overhead + OS

## Recommended Settings for Render Free Tier

### In Render Environment Variables:

```
ABSOLUTE_MAX_FILE_SIZE=52428800
```
(That's **50MB** - safe limit for free tier)

### Why 50MB?
- 50MB file → ~200MB RAM usage
- Leaves 312MB for OS + Python + overhead
- Safe margin for multiple concurrent requests

## If You Need Larger Files

### Option 1: Upgrade to Starter Plan ($7/mo)
- Still 512MB RAM, but dedicated
- Better performance, no spin-down
- Can handle 50-75MB files more reliably

### Option 2: Upgrade to Standard Plan ($25/mo)
- **2GB RAM** - Can handle 200-500MB files
- Dedicated resources
- Better for production use

### Option 3: Optimize Processing (Advanced)
- Process chunks sequentially instead of parallel (slower but uses less memory)
- Set `MAX_PARALLEL_WORKERS=1` to reduce memory
- Trade speed for memory safety

## Current Server Configuration

Check your Render environment variables:

```bash
# Critical settings for Free Tier:
ABSOLUTE_MAX_FILE_SIZE=52428800     # 50MB (REQUIRED for free tier)
MAX_PARALLEL_WORKERS=1              # Sequential processing (safer)
MAX_CONCURRENT_JOBS=3               # Limit simultaneous uploads
RAM_SAFETY_MARGIN=0.6               # More conservative (60% instead of 70%)
```

## How to Fix Your Current Issue

### Step 1: Lower File Size Limit (NOW)
1. Go to Render Dashboard
2. Environment tab
3. Edit `ABSOLUTE_MAX_FILE_SIZE`
4. Set to: `52428800` (50MB)
5. Save and wait for redeploy

### Step 2: Reduce Parallel Workers
1. In same Environment tab
2. Edit `MAX_PARALLEL_WORKERS`
3. Set to: `1` (sequential processing)
4. Save

### Step 3: Test with Smaller Files
After redeploy, test with:
- ✅ 5MB PDF - Should work instantly
- ✅ 20MB PDF - Should process in ~15-30 seconds
- ⚠️ 40MB PDF - Should work but takes ~1-2 minutes
- ❌ 60MB+ PDF - Will be rejected at upload

## Monitoring Memory Usage

Your `/health` endpoint shows current memory:

```javascript
fetch('https://watermarks-backend.onrender.com/health')
  .then(r => r.json())
  .then(data => {
    console.log('Available RAM:', data.memory.available_mb + 'MB');
    console.log('Memory used:', data.memory.percent_used + '%');
  });
```

**Warning signs:**
- `percent_used > 80%` → Server struggling
- `available_mb < 100` → About to crash
- `active_jobs > 3` → Too many concurrent uploads

## Frontend Changes Recommended

Add file size validation BEFORE upload:

```javascript
// In your frontend upload handler
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

function handleFileUpload(file) {
  if (file.size > MAX_FILE_SIZE) {
    alert('File too large! Maximum size: 50MB on free plan');
    return;
  }
  
  // Show warning for files > 30MB
  if (file.size > 30 * 1024 * 1024) {
    const confirmMsg = 'File is large (> 30MB). Processing may take 1-2 minutes. Continue?';
    if (!confirm(confirmMsg)) return;
  }
  
  // Proceed with upload...
}
```

## Signs You Need to Upgrade

Upgrade to paid tier if you experience:
- ✅ Server crashes frequently
- ✅ Need to process 75MB+ files
- ✅ Multiple users uploading simultaneously
- ✅ Processing takes > 3 minutes
- ✅ Users complaining about slow/unreliable service

## Quick Fix Checklist

- [ ] Set `ABSOLUTE_MAX_FILE_SIZE=52428800` in Render
- [ ] Set `MAX_PARALLEL_WORKERS=1` in Render
- [ ] Set `MAX_CONCURRENT_JOBS=3` in Render
- [ ] Wait for redeploy (~2-3 minutes)
- [ ] Test with 10MB file first
- [ ] Add file size warning in frontend
- [ ] Monitor `/health` endpoint during processing
- [ ] Consider upgrade if crashes persist

## Memory-Safe Configuration (Copy-Paste)

Use these exact values in **Render Environment Variables**:

```
DEBUG=False
ABSOLUTE_MAX_FILE_SIZE=52428800
MAX_PARALLEL_WORKERS=1
MAX_CONCURRENT_JOBS=3
RAM_SAFETY_MARGIN=0.6
MIN_FREE_RAM_REQUIRED=104857600
DEFAULT_CHUNK_SIZE=10
CORS_ORIGINS=http://localhost:3000,https://yuanfengli168.github.io
```

---

**Bottom Line:** Free tier = 50MB max files, 1 worker, 3 concurrent jobs. Anything more requires paid plan.
