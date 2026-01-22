# Deployment Guide - Render 512MB Tier

## Overview

This application is optimized for deployment on Render's free tier (512MB RAM limit) using a SQLite database backend.

## Prerequisites

- Render account (free tier works)
- GitHub repository connected to Render
- Environment variable: `OPENAI_API_KEY`

## Quick Deploy to Render

### 1. Create Web Service

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Name**: `daiy-demo` (or your choice)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --workers 1 --timeout 120 --bind 0.0.0.0:$PORT web.app:app`
   - **Plan**: `Free` (512MB RAM)

> **Note**: The `--timeout 120` flag is essential for LLM calls which can take 30-60 seconds. Without it, gunicorn's default 30s timeout will cause 502 errors.

### 2. Environment Variables

Add in Render dashboard under "Environment":

```
OPENAI_API_KEY=sk-...your-key...
```

Optional (for basic auth):
```
DEMO_USER=demo
DEMO_PASS=your-password
```

### 3. Database Setup

The application expects an existing SQLite database file; it is not created automatically from the CSV on first run. You must either commit a prebuilt database to the repo or create it using the build command described in **Option B** below.

**Important**: On Render free tier, the filesystem is ephemeral. To persist data:

#### Option A: Use Persistent Disk (Recommended)

1. In Render dashboard, go to your service
2. Add a "Persistent Disk":
   - **Mount Path**: `/opt/render/project/src/data`
   - **Size**: 1 GB (more than enough for 45MB database)
3. Deploy

#### Option B: Build Database at Deploy Time

Add to Build Command:
```bash
pip install -r requirements.txt && python -c "
import pandas as pd
import sqlite3
from pathlib import Path

csv_path = 'data/bc_products_sample.csv'
db_path = 'data/products.db'

if not Path(db_path).exists():
    print('Creating database from CSV...')
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    chunk_size = 1000
    first = True
    with sqlite3.connect(db_path) as conn:
        for chunk in pd.read_csv(csv_path, chunksize=chunk_size, low_memory=False):
            chunk.to_sql('products', conn, if_exists='append' if not first else 'replace', index=False)
            first = False
        conn.execute('CREATE INDEX IF NOT EXISTS idx_category ON products(category)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_name ON products(name)')
    print('Database created successfully')
"
```

### 4. Deploy

Click "Manual Deploy" or push to your main branch for auto-deploy.

## Memory Usage

### Expected Memory on Render

- **Startup**: ~150-180MB
- **Idle**: ~150MB
- **Per Request**: +5-20MB (temporary spike)
- **Peak**: <100MB

**Well under the 512MB limit!** ✅

### Memory Optimization

The app uses lightweight SQL queries instead of loading the full product catalog (~11k products, ~300MB) into memory:
- `get_categories()` - SQL `SELECT DISTINCT` instead of loading all data
- `validate_categories()` - Uses above for validation
- `select_candidates_dynamic()` - Queries only matching products with `LIMIT`

### Monitoring

Check memory usage in Render dashboard under "Metrics".

If you see memory issues:
1. Check if database is being loaded multiple times
2. Verify indexes exist: `sqlite3 data/products.db ".indexes products"`
3. Check query result sizes in logs

### Error Tracking

The application includes a comprehensive error tracking system that persists across deployments:

**Error Types:**
- `llm_error` - OpenAI API errors, rate limits, parsing failures
- `validation_error` - Invalid user input
- `database_error` - Query failures
- `processing_error` - Image processing issues
- `unexpected_error` - Uncaught exceptions with full stack traces

**Access Error Logs:**

After deploying the error tracking system, use the Render CLI to view errors:

```bash
# Install and authenticate Render CLI (one-time setup)
brew install render  # or npm install -g render
render login

# View error summary from deployed service
make render-errors

# Filter by error type
make render-errors-type TYPE=llm_error

# Export errors for analysis
make render-errors-export OUTPUT=errors.json
```

**Local Development:**
```bash
# View errors from local database
make errors
python web/view_errors.py --all
python web/view_errors.py --type llm_error
python web/view_errors.py --export json
```

All errors stored in `data/products.db` (error_log table) persist across redeployments. See [RENDER_ERROR_LOGS.md](RENDER_ERROR_LOGS.md) for detailed guide.

## Performance

- **Cold start**: ~3-5 seconds (first request after sleep)
- **Warm requests**: <500ms
- **Database queries**: <100ms (indexed)
- **LLM calls**: 2-5 seconds (OpenAI API)

## Troubleshooting

### 1. "Out of memory" errors

**Check memory usage:**
```python
import psutil
process = psutil.Process()
print(f"Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB")
```

**Common causes:**
- Multiple workers (use 1 worker for free tier)
- Loading full catalog instead of querying
- Memory leak in long-running process

**Fix:**
```bash
# In Render, use single worker
gunicorn --workers 1 --bind 0.0.0.0:10000 web.app:app
```

### 2. Database not found

**Check if CSV exists:**
```bash
ls -lh data/bc_products_sample.csv
```

**Manually create database:**
```bash
python -c "
from web.catalog import _get_db_connection
import pandas as pd

df = pd.read_csv('data/bc_products_sample.csv', low_memory=False)
with _get_db_connection() as conn:
    df.to_sql('products', conn, if_exists='replace', index=False)
    conn.execute('CREATE INDEX idx_category ON products(category)')
"
```

### 3. Slow queries

**Check indexes exist:**
```bash
sqlite3 data/products.db "SELECT name FROM sqlite_master WHERE type='index'"
```

**Expected output:**
```
idx_category
idx_name
```

**Add if missing:**
```bash
sqlite3 data/products.db "CREATE INDEX idx_category ON products(category)"
```

### 4. Free tier limitations

Render free tier has:
- **Sleep after 15min inactivity** - First request wakes it up (3-5s delay)
- **750 hours/month** - Automatic shutdown if exceeded
- **Limited bandwidth** - Fine for demos

## Testing & Verification

### Pre-Deployment Checklist

- [ ] `OPENAI_API_KEY` set in Render environment
- [ ] Database file exists (`data/products.db`) or persistent disk configured
- [ ] Build command includes database creation (if needed)
- [ ] Start command uses `--workers 1` and `--timeout 120`
- [ ] Error tracking system deployed (`web/error_logging.py`, `web/view_errors.py`)
- [ ] Render CLI installed and authenticated for error log access
- [ ] All tests passing: `pytest web/tests/ -v`

### Post-Deployment Verification

1. **Health check:**
   ```bash
   curl https://your-app.onrender.com/
   ```

2. **Make test recommendation:**
   ```bash
   curl -X POST https://your-app.onrender.com/api/recommend \
     -H "Content-Type: application/json" \
     -d '{"problem_text": "I need to upgrade my cassette to 11-speed"}'
   ```

3. **Check error logs:**
   ```bash
   make render-errors
   ```

4. **Monitor metrics:**
   - Render dashboard → Logs tab
   - Memory usage (<512MB)
   - Response times (<5s)
   - Error rates

5. **Test flows:**
   - Simple recommendations
   - Clarification questions
   - Image upload (if applicable)

## Production Deployment

For production with higher traffic:

### Option 1: Render Paid Tier ($7/month)
- 512MB → 2GB RAM
- No sleep
- Better performance

### Option 2: Add PostgreSQL
If you need remote database access:

1. Add PostgreSQL database in Render
2. Update `web/catalog.py` to support PostgreSQL:
   ```python
   DATABASE_URL = os.getenv("DATABASE_URL")
   if DATABASE_URL:
       # Use psycopg2 for PostgreSQL
       # ... (would need code changes)
   else:
       # Use SQLite (current)
   ```

### Option 3: Scale Horizontally
Deploy multiple instances behind a load balancer.

## Environment-Specific Settings

### Development
```bash
FLASK_DEBUG=True
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
```

### Production (Render)
```bash
FLASK_DEBUG=False
FLASK_HOST=0.0.0.0
FLASK_PORT=10000
```

## Updating Data

### To update products in production:

1. **Run scraper locally:**
   ```bash
   python -m scrape.cli --max-pages 10
   ```

2. **Upload database to Render:**
   - If using persistent disk: Upload via Render dashboard
   - If not: Include in repository (not recommended for large files)

3. **Restart service:**
   - Render dashboard → Manual Deploy
   - Or: Push to trigger auto-deploy

## Security

### Basic Auth (Optional)

Protect your demo with basic authentication:

1. Set environment variables in Render:
   ```
   DEMO_USER=your-username
   DEMO_PASS=your-password
   ```

2. Users will be prompted for credentials when accessing the site

### API Keys

- Never commit `OPENAI_API_KEY` to repository
- Always use environment variables
- Rotate keys regularly

## Cost Optimization

**Free Tier (Current Setup):**
- Render: Free (512MB)
- OpenAI: Pay per use (~$0.01-0.10 per recommendation)

**Total: ~$0-5/month** depending on usage

**To reduce OpenAI costs:**
- Use cheaper models (gpt-3.5-turbo vs gpt-4)
- Cache common responses
- Implement rate limiting

## Monitoring

### Key Metrics

1. **Memory usage** - Should stay under 250MB
2. **Response time** - Target <1s for non-LLM calls
3. **Error rate** - Should be <1%
4. **Database size** - Monitor growth

### Logs

View logs in Render dashboard:
- Recent logs shown in real-time
- Search for errors: "ERROR" or "Exception"
- Check memory warnings: "memory" or "oom"

## Support

For issues:
1. Check logs in Render dashboard
2. Verify [PIPELINE.md](PIPELINE.md) for data flow
3. Check [web/README.md](web/README.md) for architecture details

## Success Checklist

Before going live:

- [ ] Environment variables set (OPENAI_API_KEY)
- [ ] Database created (45.6 MB file)
- [ ] Basic auth configured (optional)
- [ ] Memory usage verified (<250MB)
- [ ] Test scraper → web app pipeline
- [ ] Health check endpoint responding
- [ ] Error handling tested
- [ ] Logs reviewing properly

🎉 **Ready to deploy!**
