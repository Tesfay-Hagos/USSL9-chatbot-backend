# Render Deployment Guide

## Quick Setup via Render Dashboard (FREE TIER - No Payment Card Required)

### ⚠️ Important: Use "Web Service" NOT "Blueprint"
- **Web Service** = Free tier available, no payment card needed
- **Blueprint** = May require payment card even for free services

### 1. Connect GitHub Repository
- Go to Render Dashboard → **New → Web Service** (NOT Blueprint)
- Connect your GitHub account
- Select repository: `RAG-based-chatbot`
- Select branch: `main`

### 2. Basic Settings

**Name:**
```
univr-chatbot-backend
```

**Region:**
```
Oregon (US West)
```
(or your preferred region)

**Root Directory:**
```
(Leave EMPTY)
```
⚠️ **Important:** 
- If your GitHub repo is `univr-chatbot-backend` (backend-only repo), leave Root Directory **EMPTY**
- Only set Root Directory if your repo is a monorepo with both frontend and backend folders

**Branch:**
```
main
```

### 3. Build & Start Commands

**Build Command:**
```bash
pip install -r requirements.txt
```

**Start Command:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

⚠️ **Important:** Render automatically sets the `$PORT` environment variable. Do NOT use a hardcoded port number.

### 4. Instance Type
- **Select "Free"** - This is available when using "Web Service" (not Blueprint)
- Free tier: 512 MB RAM, 0.1 CPU
- ⚠️ Note: Free services spin down after 15 minutes of inactivity
- For production, consider Starter ($7/month) later

### 5. Environment Variables

Add these in the Render dashboard under "Environment Variables":

| Variable Name | Value | Notes |
|--------------|-------|-------|
| `GEMINI_API_KEY` | `your-actual-api-key` | **Required** - Get from [Google AI Studio](https://aistudio.google.com/) |
| `MODEL` | `gemini-2.5-flash` | Optional - Default model |
| `STORE_PREFIX` | `univr-chatbot` | Optional - Prefix for vector stores |
| `APP_ENV` | `production` | Optional - Environment mode |
| `DEBUG` | `false` | Optional - Set to `false` for production |
| `PORT` | (auto-set) | **Auto-set by Render** - Don't override |

### 6. Health Check (Optional)
- **Health Check Path:** `/health`
- Render will use this to verify your service is running

### 7. Deploy!

Click "Create Web Service" and Render will:
1. Clone your repository
2. Install dependencies from `requirements.txt`
3. Start your FastAPI app
4. Provide a public URL (e.g., `https://univr-chatbot-backend.onrender.com`)

---

## Alternative: Use render.yaml (Requires Payment Card)

⚠️ **Note:** Blueprints may require a payment method even for free services.

If you want to use `render.yaml`:
1. Go to Render Dashboard → New → Blueprint
2. Connect your GitHub repository
3. Render will automatically detect and use `render.yaml`
4. You may need to add a payment method (but can still select free tier)

**For free tier without payment card, use the manual "Web Service" method above.**

---

## Post-Deployment

### Update Frontend API URL

After deployment, update your frontend to use the Render URL:

1. In `univr-chatbot-front/.env.local` or environment variables:
   ```
   NEXT_PUBLIC_API_URL=https://univr-chatbot-backend.onrender.com/api
   ```

2. Or update `univr-chatbot-front/lib/api.ts`:
   ```typescript
   const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://univr-chatbot-backend.onrender.com/api';
   ```

### Test Your Deployment

1. Health check: `https://your-app.onrender.com/health`
2. API docs: `https://your-app.onrender.com/docs` (FastAPI auto-generated)
3. Test chat endpoint: `https://your-app.onrender.com/api/chat`

---

## Troubleshooting

### Service won't start
- Check logs in Render dashboard
- Verify `GEMINI_API_KEY` is set correctly
- Ensure start command uses `$PORT` (not hardcoded)

### Build fails
- Check Python version (should be 3.12+)
- Verify `requirements.txt` exists and is valid
- Check build logs for specific errors

### CORS errors
- The app already has CORS middleware allowing all origins
- If issues persist, check frontend API URL configuration

---

## Notes

- Render free tier services **spin down after 15 minutes of inactivity**
- First request after spin-down may take 30-60 seconds
- Consider paid tier for production to avoid spin-downs
- Monitor logs in Render dashboard for any issues
