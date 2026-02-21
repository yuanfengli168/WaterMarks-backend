# Deployment Guide - Render

## Prerequisites
- GitHub account
- Render account (free tier available at https://render.com)
- This repository pushed to GitHub

---

## Step 1: Prepare for Deployment

### 1.1 Update Environment Variables
In your Render dashboard, you'll set these environment variables:

**Required:**
```
DEBUG=False
HOST=0.0.0.0
PORT=10000
```

**CORS (Update with your GitHub Pages URL):**
```
CORS_ORIGINS=https://yourusername.github.io,https://your-frontend-domain.com
```

**File Size Limits (adjust based on Render tier):**
```
RAM_SAFETY_MARGIN=0.7
ABSOLUTE_MAX_FILE_SIZE=104857600
MIN_FREE_RAM_REQUIRED=52428800
```

**Processing:**
```
MAX_PARALLEL_WORKERS=2
DEFAULT_CHUNK_SIZE=10
```

**Watermark Settings:**
```
WATERMARK_TEXT=WATERMARK
WATERMARK_FONT_SIZE=60
WATERMARK_OPACITY=0.3
WATERMARK_ROTATION=45
```

---

## Step 2: Deploy to Render

### Option A: Deploy via Render Dashboard

1. **Go to Render Dashboard**
   - Visit https://dashboard.render.com
   - Click "New +" → "Web Service"

2. **Connect GitHub Repository**
   - Select "Build and deploy from a Git repository"
   - Connect your GitHub account
   - Select the WaterMarks-backend repository

3. **Configure Service**
   ```
   Name: watermarks-backend (or your choice)
   Region: Oregon (US West) or closest to your users
   Branch: main
   Runtime: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: uvicorn app:app --host 0.0.0.0 --port $PORT
   ```

4. **Choose Plan**
   - Free tier: 512 MB RAM, spins down after inactivity
   - Starter: $7/mo, 512 MB RAM, always on
   - (Recommend Starter for production to avoid cold starts)

5. **Set Environment Variables**
   - Click "Advanced" → "Add Environment Variable"
   - Add all variables from Step 1.1 above
   - **Important:** Set `DEBUG=False` for production

6. **Deploy**
   - Click "Create Web Service"
   - Wait 5-10 minutes for first deployment
   - Your service will be at: `https://your-service-name.onrender.com`

### Option B: Deploy via render.yaml (Infrastructure as Code)

Create `render.yaml` in repository root (already created).

Push to GitHub and Render will auto-detect the configuration.

---

## Step 3: Configure CORS for Your Frontend

**Option 1: Set specific domains (recommended for production)**

In Render's Environment Variables:
```
CORS_ORIGINS=https://yourusername.github.io,https://your-custom-domain.com
```

**Option 2: Allow all origins (for testing only)**

Set in Render:
```
DEBUG=True
```
This allows all origins but should NOT be used in production.

---

## Step 4: Update Frontend API URL

In your frontend code, update the API base URL:

```javascript
// Development
const API_URL = "http://localhost:8000";

// Production
const API_URL = "https://your-service-name.onrender.com";

// Or use environment variable
const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";
```

---

## Step 5: Test Deployment

### 5.1 Health Check
```bash
curl https://your-service-name.onrender.com/health
```

Expected response:
```json
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

### 5.2 Test Size Check
```bash
curl -X POST https://your-service-name.onrender.com/api/check-size \
  -H "Content-Type: application/json" \
  -d '{"file_size": 1048576}'
```

### 5.3 View API Documentation
Visit: `https://your-service-name.onrender.com/docs`

---

## Step 6: Handle Render Free Tier Limitations

**Free Tier spins down after 15 minutes of inactivity.**

### Create a Wake-Up Function in Frontend

```javascript
// Wake up the server before making real requests
async function wakeUpServer() {
  try {
    const response = await fetch(`${API_URL}/ping`);
    return response.ok;
  } catch (error) {
    console.error("Server wake-up failed:", error);
    return false;
  }
}

// Use before upload
async function uploadPDF(file) {
  showMessage("Waking up server...");
  await wakeUpServer();
  
  // Small delay to ensure server is ready
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  // Now proceed with actual upload
  showMessage("Uploading PDF...");
  // ... rest of upload logic
}
```

### Or Use a Cron Job Service

Set up a free service like cron-job.org to ping your endpoint every 10 minutes:
- URL: `https://your-service-name.onrender.com/ping`
- Interval: Every 10 minutes

**Note:** This keeps the server warm but uses free tier hours.

---

## Step 7: Monitor Deployment

### Render Dashboard
- View logs: Click service → "Logs" tab
- Monitor metrics: CPU, Memory, Request count
- Check deployments: See deploy history and status

### Check Logs
```bash
# Logs are available in Render dashboard
# Or use Render CLI
render logs -s your-service-name --tail
```

---

## Production Configuration Recommendations

### For Free Tier (512 MB RAM)
```
ABSOLUTE_MAX_FILE_SIZE=104857600  # 100MB max
RAM_SAFETY_MARGIN=0.6             # Use 60% of RAM
MAX_PARALLEL_WORKERS=2            # Limit parallelism
```

### For Starter Tier (512 MB RAM, always on)
```
ABSOLUTE_MAX_FILE_SIZE=209715200  # 200MB max
RAM_SAFETY_MARGIN=0.7             # Use 70% of RAM
MAX_PARALLEL_WORKERS=3
```

### For Professional Tier (2 GB+ RAM)
```
ABSOLUTE_MAX_FILE_SIZE=524288000  # 500MB max
RAM_SAFETY_MARGIN=0.7
MAX_PARALLEL_WORKERS=4
```

---

## Troubleshooting

### Issue: CORS Errors
**Solution:** Check CORS_ORIGINS includes your frontend domain
```bash
# In Render dashboard, verify environment variable:
CORS_ORIGINS=https://yourusername.github.io
```

### Issue: 500 Internal Server Error
**Solution:** Check logs in Render dashboard for Python errors

### Issue: Out of Memory
**Solution:** 
- Reduce ABSOLUTE_MAX_FILE_SIZE
- Reduce MAX_PARALLEL_WORKERS
- Lower RAM_SAFETY_MARGIN
- Upgrade Render plan

### Issue: Slow Cold Starts (Free Tier)
**Solution:**
- Add wake-up endpoint call in frontend
- Upgrade to Starter plan ($7/mo) for always-on
- Set up cron job to keep warm

### Issue: File Upload Timeout
**Solution:**
- Render free tier has 30-second request timeout
- For large files, ensure they're within size limits
- Consider upgrading plan for longer timeouts

---

## Auto-Deploy Setup

### Enable Auto-Deploy from GitHub

In Render Dashboard:
1. Go to your service settings
2. Find "Auto-Deploy" section
3. Enable "Auto-Deploy: Yes"

Now every push to `main` branch will auto-deploy!

---

## Custom Domain (Optional)

1. In Render Dashboard → Service → "Settings"
2. Scroll to "Custom Domain"
3. Add your domain: `api.yourdomain.com`
4. Follow DNS configuration instructions
5. Update CORS_ORIGINS to include new domain

---

## Security Recommendations

1. **Never commit `.env` file** (already in .gitignore)
2. **Set DEBUG=False in production**
3. **Restrict CORS_ORIGINS** to only your frontend domains
4. **Monitor logs** for unusual activity
5. **Set file size limits** appropriate for your plan
6. **Consider adding rate limiting** for production
7. **Use HTTPS only** (Render provides free SSL)

---

## Cost Estimate

- **Free Tier**: $0/month (750 hours/month, spins down after inactivity)
- **Starter**: $7/month (always on, 512 MB RAM)
- **Standard**: $25/month (2 GB RAM)
- **Pro**: $85/month (4 GB RAM)

For testing/demo: Free tier is sufficient
For production: Starter or Standard recommended

---

## Next Steps After Deployment

1. ✅ Test all endpoints from frontend
2. ✅ Verify file upload works
3. ✅ Test error handling
4. ✅ Monitor initial usage
5. ✅ Adjust file size limits based on usage
6. ✅ Set up monitoring alerts (Render provides basic monitoring)

---

## Support

- Render Docs: https://render.com/docs
- Render Community: https://community.render.com
- Your API Docs: `https://your-service-name.onrender.com/docs`

---

## Quick Checklist

- [ ] Repository pushed to GitHub
- [ ] Render account created
- [ ] Service deployed on Render
- [ ] Environment variables set
- [ ] CORS configured for frontend domain
- [ ] Health check working
- [ ] Frontend updated with production API URL
- [ ] Test upload working
- [ ] Monitoring set up
