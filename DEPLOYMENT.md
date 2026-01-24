# Render Deployment Guide

Quick reference for deploying Daiy to Render's free tier (512MB RAM).

## Prerequisites

- Render account (free tier available)
- GitHub repository connected to Render
- OpenAI API key
- Python 3.8+

## Quick Deploy

### 1. Create Web Service on Render

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Name**: `daiy-demo` (or your choice)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --workers 1 --timeout 120 --bind 0.0.0.0:$PORT web.app:app`
   - **Plan**: `Free` (512MB RAM)

> **Note**: The `--timeout 120` flag is essential for LLM calls which can take 30-60 seconds.

### 2. Add Environment Variables

In Render dashboard under "Environment", add:

**Required:**
```
OPENAI_API_KEY=sk-...your-key...
FLASK_SECRET_KEY=<generate-a-random-hex-string>
```

**Important**: Generate a random secret key for `FLASK_SECRET_KEY`. Example:
```bash
python -c "import os; print(os.urandom(32).hex())"
```

> **Important**: `FLASK_SECRET_KEY` is required for session cookies (used by the consent page) to work correctly. Without it, a random key is generated on each deployment, invalidating all existing sessions. Generate one with: `python -c "import secrets; print(secrets.token_hex(32))"`

**Optional:**
```
DEMO_USER=demo
DEMO_PASS=your-password
```

### 3. Add Persistent Disk

Data persists across redeployments:

1. Go to your Render service
2. Add "Persistent Disk":
   - **Mount Path**: `/opt/render/project/src/data`
   - **Size**: 1 GB

3. Deploy

## Memory Usage

The app fits the 512MB tier:
- **Startup**: ~150-180MB
- **Idle**: ~150MB
- **Per Request**: +5-20MB (spike)
- **Peak**: <100MB

Database queries are memory-efficient (SQLite on disk, not in RAM).

## Monitoring

### Error Logs

All errors persist in SQLite database across redeployments. View from local machine:

```bash
# Install Render CLI (one-time)
brew install render  # or npm install -g render

# Authenticate
render login

# View errors from deployed service
make render-errors
```

See [RENDER_ERROR_LOGS.md](RENDER_ERROR_LOGS.md) for detailed CLI commands.

### Performance

Check Render dashboard under "Metrics" for:
- Memory usage
- CPU usage
- Request count
- Response times

## Troubleshooting

### Memory Issues

Check memory usage in Render dashboard. If high:

1. Verify database queries are using indexes:
   ```bash
   sqlite3 data/products.db ".indexes products"
   ```

2. Check logs for repeated queries
3. Monitor with `top` or dashboard metrics

### Deploy Failures

1. Check build logs in Render dashboard
2. Verify `requirements.txt` all packages install
3. Test locally: `gunicorn --workers 1 --timeout 120 --bind 0.0.0.0:5000 web.app:app`

### LLM Timeouts

If you see 502 errors during LLM calls:
- Verify `--timeout 120` in gunicorn command
- Check OpenAI API status page
- Try again (rate limits resolve in 60 seconds)

## Database Setup

The app requires a pre-populated SQLite database. Two options:

### Option A: Use Existing Database (Recommended)

The repository includes `data/bc_products_sample.csv`. The database is auto-created from this CSV on first run.

### Option B: Build from Scraper

Scrape fresh data from bike-components.de:

```bash
python -m scrape.cli --mode full
```

This populates `data/products.db` with ~11k products (~45MB).

## Logging

All interactions and errors persist in SQLite:
- Error logs: Queryable via `python web/view_errors.py`
- Interaction logs: Queryable via `python web/view_logs.py --db sqlite`

See [web/README.md](web/README.md#error-tracking--monitoring) and [web/README.md](web/README.md#interaction-logging) for details.

## Local Development

Test deployment locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Set API key
export OPENAI_API_KEY="sk-..."

# Run with gunicorn (same as Render)
gunicorn --workers 1 --timeout 120 --bind 0.0.0.0:5000 web.app:app

# Visit http://localhost:5000
```

Or use the Flask development server:

```bash
python web/app.py
```

## See Also

- [web/README.md](web/README.md) - Web app documentation
- [RENDER_ERROR_LOGS.md](RENDER_ERROR_LOGS.md) - Remote error monitoring CLI
- [QUICKSTART.md](QUICKSTART.md) - Getting started locally
- [README.md](README.md) - Project overview
