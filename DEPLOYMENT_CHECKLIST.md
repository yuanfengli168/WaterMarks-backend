# Deployment Checklist

Before deploying your PDF Watermark Backend to Render, ensure you've completed these steps:

## Pre-Deployment Preparation

### 1. Environment Configuration ✓
- [x] `.env.example` created with production settings
- [ ] Review and adjust `ABSOLUTE_MAX_FILE_SIZE` for your Render tier:
  - Free tier (512MB RAM): 100MB (104857600 bytes)
  - Starter tier (512MB RAM): 200MB (209715200 bytes)  
  - Standard tier (2GB RAM): 500MB+ (524288000 bytes)
- [ ] Update `CORS_ORIGINS` with your GitHub Pages URL:
  - Example: `https://yourusername.github.io`
  - Or use wildcard: `https://*.github.io` (already in config)

### 2. Code Repository ✓
- [x] All code committed to Git
- [ ] Push to GitHub:
  ```bash
  git add .
  git commit -m "Ready for Render deployment"
  git push origin main
  ```

### 3. Dependencies Verified ✓
- [x] `requirements.txt` includes all dependencies
- [x] Versions specified for stability:
  - FastAPI==0.109.0
  - PyPDF2==3.0.1
  - reportlab==4.0.9
  - psutil==5.9.8

### 4. Render Configuration ✓
- [x] `render.yaml` created with proper settings
- [ ] Review `render.yaml` settings:
  - `buildCommand`: `pip install -r requirements.txt`
  - `startCommand`: `uvicorn app:app --host 0.0.0.0 --port $PORT`
  - `plan`: free (or change to starter/standard)

## Deployment to Render

### Step 1: Create Render Account
1. Go to [https://render.com](https://render.com)
2. Sign up or log in
3. Connect your GitHub account

### Step 2: Create New Web Service
1. Click "New +" → "Web Service"
2. Connect your GitHub repository: `WaterMarks-backend`
3. Configure:
   - **Name**: `watermarks-api` (or your choice)
   - **Environment**: Python 3
   - **Region**: Choose closest to your users
   - **Branch**: main
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`

### Step 3: Set Environment Variables
Add these in Render Dashboard under "Environment":

**Required:**
```
DEBUG=False
ABSOLUTE_MAX_FILE_SIZE=104857600
MAX_PARALLEL_WORKERS=2
MAX_CONCURRENT_JOBS=5
```

**CORS (update with YOUR domain):**
```
CORS_ORIGINS=http://localhost:3000,https://yourusername.github.io
```

**Optional (use defaults if not set):**
```
RAM_SAFETY_MARGIN=0.7
MIN_FREE_RAM_REQUIRED=104857600
DEFAULT_CHUNK_SIZE=10
WATERMARK_TEXT=WATERMARK
WATERMARK_FONT_SIZE=60
WATERMARK_OPACITY=0.3
WATERMARK_ROTATION=45
TEMP_DIR=temp_files
JOB_RETENTION_HOURS=1
RECHECK_SIZE_ON_UPLOAD=True
```

### Step 4: Deploy
1. Click "Create Web Service"
2. Wait for build to complete (~5-10 minutes)
3. Your API will be available at: `https://your-service-name.onrender.com`

### Step 5: Verify Deployment
Test your deployed API:

```bash
# Test health endpoint
curl https://your-service-name.onrender.com/health

# Expected response:
{
  "status": "healthy",
  "server": "running",
  "active_jobs": 0,
  "memory": {
    "available_mb": 350.5,
    "percent_used": 31.5
  },
  "uptime": "ok"
}
```

```bash
# Test ping endpoint
curl https://your-service-name.onrender.com/ping

# Expected response:
{"pong": true, "timestamp": 1234567890.123}
```

## Post-Deployment Tasks

### 1. Update Frontend Configuration
Update your frontend code with the Render API URL:

```javascript
// In your frontend config
const API_URL = 'https://your-service-name.onrender.com';

// Or use environment variable
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
```

### 2. Test Full Workflow
1. Open your frontend (GitHub Pages)
2. Try uploading a small PDF (< 1MB)
3. Verify status updates appear correctly
4. Download the watermarked PDF
5. Check for CORS errors in browser console

### 3. Free Tier Considerations

**Important:** Render Free tier spins down after 15 minutes of inactivity.

**Option A: Implement Wake-up Call (Recommended)**
In your frontend, add this before the first API call:

```javascript
async function wakeUpServer() {
  try {
    await fetch(`${API_URL}/ping`);
    // Wait a moment for server to fully wake
    await new Promise(resolve => setTimeout(resolve, 2000));
  } catch (error) {
    console.log('Server waking up...');
  }
}

// Call before uploading
await wakeUpServer();
await uploadFile();
```

**Option B: Keep-alive Service (External)**
- Use cron-job.org or UptimeRobot
- Ping `/ping` endpoint every 14 minutes
- **Note:** Render free tier has 750 hours/month limit

**Option C: Upgrade to Starter Plan**
- $7/month for always-on service
- No spin-down delays
- Better performance

### 4. Monitor and Debug

**View Logs:**
1. Go to Render Dashboard
2. Click your service
3. Click "Logs" tab
4. Watch for errors or warnings

**Common Issues:**

**Problem:** 502 Bad Gateway
- **Cause:** App crashed or didn't start
- **Solution:** Check logs for Python errors, verify requirements.txt

**Problem:** CORS errors in frontend
- **Cause:** CORS_ORIGINS not set correctly
- **Solution:** Add your exact GitHub Pages URL to CORS_ORIGINS

**Problem:** "Memory exceeded" errors
- **Cause:** File size too large for free tier
- **Solution:** Reduce ABSOLUTE_MAX_FILE_SIZE or upgrade plan

**Problem:** Slow processing
- **Cause:** Free tier CPU limits
- **Solution:** Reduce MAX_PARALLEL_WORKERS to 1-2 or upgrade

### 5. Security Best Practices

- [ ] Never commit `.env` file with real secrets
- [ ] Use Render's environment variables for configuration
- [ ] Keep `DEBUG=False` in production
- [ ] Regularly update dependencies: `pip list --outdated`
- [ ] Monitor Render's security advisories

### 6. Performance Optimization

**For Free Tier:**
- Set `MAX_PARALLEL_WORKERS=2` (not 4)
- Set `ABSOLUTE_MAX_FILE_SIZE=104857600` (100MB)
- Set `MAX_CONCURRENT_JOBS=5` (not 10)
- Consider disabling heavy logging

**For Higher Tiers:**
- Increase limits based on available RAM
- Monitor memory usage via `/health` endpoint
- Adjust `RAM_SAFETY_MARGIN` if needed

## Testing Checklist

After deployment, test these scenarios:

- [ ] Small PDF (< 5MB) - Should process quickly
- [ ] Medium PDF (20-50MB) - Should process successfully
- [ ] Large PDF (near limit) - Should process or reject appropriately
- [ ] Corrupted PDF - Should return error message
- [ ] Encrypted PDF - Should return "encrypted" error
- [ ] Non-PDF file - Should return "invalid PDF" error
- [ ] Multiple concurrent uploads - Should handle gracefully
- [ ] Status polling - Should show progress updates
- [ ] Download - Should return watermarked PDF
- [ ] Cold start (after 15 min) - Should wake up and process

## Troubleshooting

**Build Fails:**
1. Check Python version in Render matches requirements
2. Verify all imports in code are in requirements.txt
3. Check Render logs for specific error

**Runtime Errors:**
1. Check environment variables are set correctly
2. Verify `/health` endpoint returns 200
3. Test locally with same environment variables
4. Check Render logs for stack traces

**Performance Issues:**
1. Reduce parallel workers
2. Decrease max file size
3. Monitor memory via `/health`
4. Consider upgrading Render plan

## Resources

- **Render Documentation**: https://render.com/docs
- **Deployment Guide**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **API Documentation**: [FRONTEND_API_DOCUMENTATION.md](FRONTEND_API_DOCUMENTATION.md)
- **Render Status Page**: https://status.render.com

## Upgrade Paths

**When to upgrade from Free to Starter ($7/mo):**
- ✓ Need always-on service (no spin-down)
- ✓ Processing > 100 files/day
- ✓ Need faster processing times
- ✓ Want better reliability

**When to upgrade to Standard ($25/mo):**
- ✓ Need to process 200MB+ files
- ✓ High traffic (100+ users/day)
- ✓ Need 2GB RAM for large PDFs
- ✓ Want dedicated resources

---

## Quick Reference

**Your API URL:** `https://your-service-name.onrender.com`

**Key Endpoints:**
- Health: `GET /health`
- Ping: `GET /ping`
- Check size: `POST /api/check-size`
- Upload: `POST /api/upload`
- Status: `GET /api/status/{job_id}`
- Download: `GET /api/download/{job_id}`
- Docs: `GET /docs`

**Support:**
- GitHub Issues: [Your repo URL]
- Render Support: https://render.com/support

---

**✓ Deployment Complete!** Your PDF Watermark Backend is now live and ready for production use.
