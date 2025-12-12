# LLM Interaction Logging

This project includes comprehensive logging of all LLM interactions to help with debugging, analysis, and understanding the system's behavior.

## Log Format

Logs are stored in `web/logs/llm_interactions_YYYYMMDD.jsonl` as JSON Lines (one JSON object per line).

Each log entry has the following structure:
```json
{
  "timestamp": "2025-12-11T10:30:45.123456",
  "event_type": "user_input",
  ...event-specific fields...
}
```

## Event Types

### 1. `user_input`
Captures when a user submits a new problem/prompt via the form. This event marks the start of a new session.
```json
{
  "timestamp": "...",
  "event_type": "user_input",
  "problem_text": "I need a new cassette for my gravel bike"
}
```

### 2. `user_selection`
Logs when the user selects an option during the clarification flow (speed or use case buttons). These events are grouped with the current session.
```json
{
  "timestamp": "...",
  "event_type": "user_selection",
  "problem_text": "I need a new cassette for my gravel bike",
  "selected_speed": 11,
  "selected_use_case": "gravel"
}
```

### 3. `regex_inference`
Shows what the regex-based inference detected.
```json
{
  "timestamp": "...",
  "event_type": "regex_inference",
  "inferred_speed": null,
  "inferred_use_case": "gravel",
  "final_speed": null,
  "final_use_case": "gravel"
}
```

### 4. `llm_call_clarification`
Logs the LLM call for clarification/inference.
```json
{
  "timestamp": "...",
  "event_type": "llm_call_clarification",
  "model": "gpt-5-mini",
  "prompt": "You are assisting...",
  "missing_keys": ["drivetrain_speed"],
  "user_text": "I need a new cassette for my gravel bike"
}
```

### 4. `llm_response_clarification`
Logs the raw LLM response for clarification.
```json
{
  "timestamp": "...",
  "event_type": "llm_response_clarification",
  "model": "gpt-5-mini",
  "raw_response": "{\"inferred_speed\": 11, \"inferred_use_case\": null, ...}"
}
```

### 5. `llm_inference_result`
### 5. `llm_inference_result`
Parsed result from the clarification LLM.
```json
{
  "timestamp": "...",
  "event_type": "llm_inference_result",
  "inferred_speed": 11,
  "inferred_use_case": null,
  "speed_options": [],
  "use_case_options": ["road", "gravel", "mtb"]
}
```

### 6. `llm_call_recommendation`
Logs the main LLM call for product recommendations.
```json
{
  "timestamp": "...",
  "event_type": "llm_call_recommendation",
  "model": "gpt-5-mini",
  "prompt": "Given this context:..."
}
```

### 7. `llm_response_recommendation`
Logs the final recommendation response.
```json
{
  "timestamp": "...",
  "event_type": "llm_response_recommendation",
  "model": "gpt-5-mini",
  "raw_response": "Based on your gravel riding needs..."
}
```

### 8. `llm_parse_error`
Logs any JSON parsing errors.
```json
{
  "timestamp": "...",
  "event_type": "llm_parse_error",
  "error": "Expecting value: line 1 column 1 (char 0)",
  "raw": "Some invalid JSON..."
}
```

## Viewing Logs

### Option 1: Use the log viewer script (Recommended)
```bash
# View today's log in browser
python web/view_logs.py

# View specific log file in browser
python web/view_logs.py web/logs/llm_interactions_20251211.jsonl
```

The viewer opens an interactive HTML file with:
- **Session-based organization**: Events grouped by user interaction sessions (one session per problem submission)
- Color-coded event types
- Collapsible prompts/responses
- Event filtering controls
- Real-time statistics
- Dark theme (easy on the eyes)

### Session Structure in Logs
Each user interaction session consists of:
1. **`user_input`** event - The initial problem submission (starts a new session)
2. **`regex_inference`** event - Regex-based attribute extraction
3. **`llm_call_clarification`** + **`llm_response_clarification`** events (if needed) - LLM inference for missing attributes
4. **`user_selection`** events (if needed) - User selecting from clarification options
5. **`llm_call_recommendation`** + **`llm_response_recommendation`** events - Final recommendation

### Option 2: Manual inspection with jq
```bash
# View all events of a specific type
cat web/logs/llm_interactions_*.jsonl | jq 'select(.event_type=="llm_call_clarification")'

# Count events by type
cat web/logs/llm_interactions_*.jsonl | jq -r '.event_type' | sort | uniq -c

# Extract all user inputs
cat web/logs/llm_interactions_*.jsonl | jq 'select(.event_type=="user_input") | .problem_text'

# View inference results
cat web/logs/llm_interactions_*.jsonl | jq 'select(.event_type=="llm_inference_result")'
```

### Option 3: Grep for specific content
```bash
# Find all sessions mentioning "gravel"
grep -i "gravel" web/logs/llm_interactions_*.jsonl

# Find errors
grep "llm_parse_error" web/logs/llm_interactions_*.jsonl
```

## Use Cases

### 1. Debugging inference issues
Track how regex and LLM inference work together:
```bash
python web/view_logs.py | grep -A5 "regex_inference"
```

### 2. Understanding LLM behavior
See exactly what prompts are sent and how the LLM responds:
```bash
python web/view_logs.py | grep -A20 "llm_call"
```

### 3. Analyzing user patterns
Extract all unique user inputs:
```bash
cat web/logs/*.jsonl | jq -r 'select(.event_type=="user_input") | .problem_text' | sort | uniq
```

### 4. Performance analysis
Count how many LLM calls are made per session (should be 1-2 max):
```bash
cat web/logs/*.jsonl | jq -r '.event_type' | grep "llm_call" | wc -l
```

### 5. Error tracking
Find all parsing errors:
```bash
cat web/logs/*.jsonl | jq 'select(.event_type=="llm_parse_error")'
```

## Log Rotation

Logs are automatically rotated daily (file name includes date). Old logs are kept unless manually deleted.

To clean up old logs:
```bash
# Delete logs older than 7 days
find web/logs/ -name "*.jsonl" -mtime +7 -delete
```

## Privacy & Security

⚠️ **Important**: Log files contain:
- User input text (may include personal information)
- Full LLM prompts and responses
- API model names

**Best practices:**
1. Logs are already excluded from git (see `.gitignore`)
2. Don't share logs publicly without redacting sensitive data
3. Rotate/delete logs regularly if they contain user data
4. Consider encrypting logs at rest for production use

## Log Structure Benefits

**JSONL format advantages:**
- Each line is a complete, parseable event
- Easy to stream and process incrementally
- Works well with Unix tools (grep, awk, etc.)
- No need to load entire file into memory
- Append-only, safe for concurrent writes

**Structured logging advantages:**
- Easy to query specific event types
- Machine-readable for analytics
- Human-readable with the viewer script
- Complete audit trail of all LLM interactions
