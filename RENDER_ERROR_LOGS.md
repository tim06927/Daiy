# Render Error Logs - Make Command Guide

## Quick Start

```bash
# View error summary from Render
make render-errors

# Export errors to JSON file
make render-errors-export OUTPUT=my_errors.json

# Filter by error type on Render
make render-errors-type TYPE=llm_error
```

## Setup (One-Time)

### Prerequisites

**⚠️ IMPORTANT**: The error tracking system must be deployed to Render before these commands will work. The remote service needs:
- `web/error_logging.py` - Error logging infrastructure
- `web/view_errors.py` - Error viewing/export script
- Error logs written to disk at runtime

After deploying the error tracking code to Render, install and authenticate with Render CLI:

```bash
# Install Render CLI
brew install render          # macOS
# or
npm install -g render        # Windows/Linux

# If you installed an alternative binary (e.g., raster3d), set:
# export RENDER_CLI=raster3d

# Authenticate
render login

# Verify it works
${RENDER_CLI:-render} services
```

## Available Commands

### `make render-errors`
View a summary of errors from your Render deployment with recent error details.

```bash
make render-errors

# Example output:
# 🔍 Fetching error logs from Render service: daiy-web-prod
# ✅ Found 12 errors
# 
# Error Summary:
#   • llm_error: 8
#   • validation_error: 3
#   • database_error: 1
#
# Recent errors:
# [1] LLM_ERROR
#     Time: 2026-01-22T14:30:45
#     Message: OpenAI API rate limited
#     Fix: Wait 60 seconds and retry
# ...
```

### `make render-errors-all`
List all errors from Render (same as `render-errors`, can specify different service).

```bash
make render-errors-all

# With specific service:
make render-errors-all SERVICE=my-other-service
```

### `make render-errors-type`
Filter and view only errors of a specific type.

```bash
make render-errors-type TYPE=llm_error
make render-errors-type TYPE=validation_error
make render-errors-type TYPE=database_error
make render-errors-type TYPE=processing_error
make render-errors-type TYPE=unexpected_error
```

### `make render-errors-export`
Export errors from Render to a JSON file for analysis or archival.

```bash
# Export to default file (render_errors_export.json)
make render-errors-export

# Export to custom file
make render-errors-export OUTPUT=errors_2026_01_22.json

# Then you can:
cat render_errors_export.json | python -m json.tool | head -50
```

## Script Details

The underlying Python script is: `scripts/get_render_errors.py`

### Direct Python Usage

```bash
# Default service (daiy-web-prod)
python scripts/get_render_errors.py

# Specific service
python scripts/get_render_errors.py my-service-name

# With output file
python scripts/get_render_errors.py daiy-web-prod errors.json

# With limit
python scripts/get_render_errors.py daiy-web-prod - 20
```

## Workflow Examples

### Daily Monitoring
```bash
# Morning check
make render-errors

# Check for specific issues
make render-errors-type TYPE=llm_error

# Export for review
make render-errors-export OUTPUT=daily_errors_$(date +%Y-%m-%d).json
```

### Debugging Session
```bash
# See what errors occurred
make render-errors

# Get more details on LLM errors
make render-errors-type TYPE=llm_error

# Save for later analysis
make render-errors-export OUTPUT=llm_errors.json
```

### Error Spike Investigation
```bash
# Quick summary
make render-errors

# Export everything
make render-errors-export OUTPUT=error_spike_analysis.json

# Review the JSON file
less error_spike_analysis.json
```

## Troubleshooting

### "Render CLI not installed or not in PATH"
```bash
# Install Render CLI
brew install render

# Or with npm
npm install -g render

# Verify installation
render --version
```

### "Not authenticated"
```bash
# Login with Render
render login

# This opens a browser to authenticate
```

### "Service not found"
```bash
# List available services
render services

# Use the correct service name with:
make render-errors-all SERVICE=correct-service-name
```

### Timeout errors
```bash
# Check if service is running on Render dashboard
# https://dashboard.render.com

# Try again - sometimes first request is slow
make render-errors
```

## Integration with Local Error Tracking

You have two ways to view errors:

| Command | Source | Use Case |
|---------|--------|----------|
| `make errors` | Local SQLite database | Development/testing locally |
| `make render-errors` | Render deployment | Production monitoring |

They work the same way but query different sources:
- `make errors` - requires app running locally
- `make render-errors` - requires Render CLI + authentication

## Tips

**Automate daily monitoring:**
```bash
#!/bin/bash
# save as scripts/daily_monitor.sh
make render-errors | tee -a logs/render_errors_log.txt
make render-errors-export OUTPUT=logs/render_errors_$(date +%Y-%m-%d).json
```

**Compare errors over time:**
```bash
# Export multiple times
make render-errors-export OUTPUT=errors_morning.json
# ... do some testing ...
make render-errors-export OUTPUT=errors_afternoon.json

# Then compare
diff -u errors_morning.json errors_afternoon.json
```

**Share error reports:**
```bash
# Export to JSON for sharing
make render-errors-export OUTPUT=error_report.json

# Slack/email the file
cat error_report.json | python -m json.tool > error_report.txt
```

---

**Need help?**
```bash
make help | grep render-errors
python scripts/get_render_errors.py --help
```
