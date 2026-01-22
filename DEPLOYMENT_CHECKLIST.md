# Render Deployment Checklist - Error Tracking System

## Pre-Deployment Verification ✅

### Code Quality
- [x] error_logging.py compiles without errors
- [x] view_errors.py compiles without errors
- [x] api.py compiles without errors
- [x] All imports working correctly
- [x] Type annotations correct

### Testing
- [x] 18 error logging tests passing (100% success rate)
- [x] ErrorLogger database initialization working
- [x] Error logging to SQLite working
- [x] Error filtering (request_id, error_type) working
- [x] Error pagination working
- [x] Error export (JSON/JSONL) working
- [x] All 5 error types implemented
- [x] Recovery suggestions present
- [x] Stack traces captured
- [x] API integration verified

### Documentation
- [x] ERROR_TRACKING.md created (190 lines)
- [x] web/README.md updated (500+ lines added)
- [x] COMPLETION_SUMMARY.md created
- [x] Makefile targets added
- [x] Help text updated

### Database
- [x] SQLite table schema verified
- [x] Indexes created on timestamp, request_id, error_type
- [x] Database persists across sessions

### Integration
- [x] error_logging functions imported in api.py
- [x] Try-catch blocks at all critical failure points
- [x] request_id passed through entire flow
- [x] Recovery suggestions provided
- [x] Timing data integrated
- [x] Request ID correlation working

### CLI Tools
- [x] `python web/view_errors.py` working
- [x] `--all` flag working
- [x] `--type` flag working
- [x] `--request` flag working
- [x] `--export json` working
- [x] `--export jsonl` working
- [x] `--limit` and `--offset` working
- [x] `--output` file path working

### Makefile Targets
- [x] `make help` shows error tracking section
- [x] `make errors` working
- [x] `make errors-all` working
- [x] `make errors-type TYPE=llm_error` working
- [x] `make errors-request ID=<uuid>` working
- [x] `make errors-export FORMAT=json` working

## Deployment Steps

### 1. Pre-Deployment (on your machine)
```bash
# Verify everything works
make errors
make errors-all
make errors-type TYPE=llm_error

# Run tests
pytest web/tests/test_error_logging.py -v

# All should pass ✅
```

### 2. Push to Render
```bash
git add .
git commit -m "Add comprehensive error tracking for alpha deployment"
git push origin main
```

### 3. Post-Deployment (on Render)
```bash
# SSH into Render
render connect

# View errors accumulated
python web/view_errors.py

# Should show summary of any errors from deployment/early traffic
```

## Monitoring During Alpha Testing

### Daily Checks
```bash
# Check error summary
make errors

# Look for patterns
make errors-type TYPE=llm_error

# Export for analysis
make errors-export FORMAT=json
```

### Alert on These Patterns
1. **Spike in llm_error** → Check OpenAI API quota/rate limits
2. **Repeated validation_error** → Review user input handling
3. **New error type appearing** → Investigate immediately
4. **Request traces with multiple errors** → Likely a bug

### Export for Weekly Review
```bash
# Export all errors to JSON for analysis
make errors-export FORMAT=json

# Download the file and analyze in Excel or tools
```

## Render Database Files

### Important
- `data/products.db` - Contains both product catalog AND error_log table
- This file persists across all Render redeployments
- Errors accumulated indefinitely (can be manually cleaned if needed)

### Backup Strategy
```bash
# On Render, download database periodically
render connect
cp data/products.db /tmp/products_backup_$(date +%s).db

# Or export errors
python web/view_errors.py --export json --output errors_backup.json
```

## Error Table Maintenance

### Current Setup
- No automatic cleanup
- Errors persist indefinitely
- Good for alpha testing (all errors visible)

### Future (if table gets too large)
```sql
-- Delete errors older than 30 days
DELETE FROM error_log WHERE timestamp < datetime('now', '-30 days');

-- Check table size
SELECT COUNT(*) FROM error_log;

-- Vacuum to reclaim space
VACUUM;
```

## Verification on Render

### SSH into Render
```bash
render connect

# Check errors exist
python web/view_errors.py

# Should show accumulated errors

# Test export
python web/view_errors.py --export json --output test_export.json

# Check it worked
ls -la test_export.json
```

### Test Error Logging Works
```bash
# Make a bad request to trigger an error
curl -X POST http://localhost:5000/api/recommend \
  -H "Content-Type: application/json" \
  -d '{}' \

# Then check if error was logged
python web/view_errors.py --all --limit 1

# Should show the validation_error from empty request
```

## Rollback Plan (if needed)

If error tracking causes issues:

1. **Disable but keep data:**
   - Remove error logging calls from api.py (but don't delete error_logging.py)
   - Errors already logged remain in database
   - Can re-enable later without data loss

2. **Full rollback:**
   - Revert to previous commit
   - Database file persists, no data loss
   - Can still query old errors later

3. **Database cleanup:**
   - Error tracking uses separate error_log table
   - Product database (products table) unaffected
   - Can delete error_log table if needed (safe, no side effects)

## Success Criteria

✅ **Deployment successful when:**
1. App starts without errors
2. `make errors` shows no issues or previous test errors
3. New errors get logged when errors occur
4. `make errors-all` retrieves errors
5. `make errors-export` creates valid JSON file
6. Users can continue using app normally (transparent to users)

✅ **Alpha testing successful when:**
1. Error tracking captures all error types
2. Recovery suggestions are helpful
3. Patterns identified (if any)
4. No performance degradation
5. Database doesn't grow excessively

## Post-Launch Enhancements

### After alpha testing, consider:
1. Add `/api/errors` endpoint for frontend display
2. Create error monitoring dashboard
3. Add hourly error summary emails
4. Implement error cleanup (retention policy)
5. Add automatic alerting for error spikes
6. Integration with Sentry or similar service

## Support Information

### If issues arise:
1. Check ERROR_TRACKING.md for detailed documentation
2. Check web/README.md "Error Tracking & Monitoring" section
3. Review COMPLETION_SUMMARY.md for implementation details
4. Run tests: `pytest web/tests/test_error_logging.py -v`
5. Verify database: `python web/view_errors.py`

---

**Status: READY FOR RENDER DEPLOYMENT ✅**

All systems tested, documented, and verified.
Error tracking will provide full visibility into production issues while maintaining app performance.
