#!/usr/bin/env python3
"""View LLM interaction logs in a readable HTML format.

Usage:
    python view_logs.py                           # View today's JSONL log (local)
    python view_logs.py logs/llm_*.jsonl          # View specific JSONL log file
    python view_logs.py --db sqlite --request abc # View request from database (production)
    python view_logs.py --db sqlite --type user_input  # View all user inputs from database
"""

import argparse
import json
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def format_timestamp(ts: str) -> str:
    """Format ISO timestamp to readable format."""
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%H:%M:%S")
    except ValueError:
        return ts


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def render_image_meta(meta: Any) -> str:
    """Render photo metadata if present."""
    if not isinstance(meta, dict) or not meta:
        return ""

    uploaded = "Yes" if meta.get("uploaded") else "No"
    received = meta.get("received_chars", 0)
    stored = meta.get("stored_chars", 0)
    truncated_120k = "Yes" if meta.get("truncated_to_120k") else "No"
    shared = "Yes" if meta.get("shared_with_llm") else "No"
    shared_chars = meta.get("shared_chars", 0)
    truncated_prompt = "Yes" if meta.get("truncated_in_prompt") else "No"

    parts = [
        f"<li><strong>Uploaded:</strong> {uploaded}</li>",
        f"<li><strong>Received chars:</strong> {received}</li>",
        f"<li><strong>Stored chars:</strong> {stored}</li>",
        f"<li><strong>Truncated to 120k:</strong> {truncated_120k}</li>",
        f"<li><strong>Shared with LLM:</strong> {shared}</li>",
        f"<li><strong>Shared chars (prompt):</strong> {shared_chars}</li>",
        f"<li><strong>Truncated in prompt:</strong> {truncated_prompt}</li>",
    ]

    return "<p><strong>📷 Photo Meta:</strong></p><ul>" + "".join(parts) + "</ul>"


def format_event_html(event: Dict[str, Any]) -> str:
    """Format a single log event as HTML."""
    event_type = event.get("event_type", "unknown")
    timestamp = format_timestamp(event.get("timestamp", ""))

    html_parts = [f'<div class="event event-{event_type}">']
    html_parts.append(f'<h3 class="event-header">[{timestamp}] {event_type.upper()}</h3>')
    html_parts.append('<div class="event-content">')

    if event_type == "user_input":
        html_parts.append("<p><strong>📝 User Input:</strong></p>")
        html_parts.append(f'<p><code>{escape_html(event.get("problem_text", ""))}</code></p>')
        
        # Show clarification answers if present
        clarifications = event.get("clarification_answers", [])
        if clarifications:
            html_parts.append("<p><strong>💡 User Clarifications:</strong></p>")
            html_parts.append("<ul>")
            for clarif in clarifications:
                spec_name = clarif.get("spec_name", "unknown")
                answer = clarif.get("answer", "")
                html_parts.append(f"<li><strong>{spec_name}:</strong> {answer}</li>")
            html_parts.append("</ul>")
        
        # Legacy selected values
        if event.get("selected_speed"):
            html_parts.append(f'<p><strong>Selected Speed:</strong> {event["selected_speed"]}</p>')
        if event.get("selected_use_case"):
            html_parts.append(
                f'<p><strong>Selected Use Case:</strong> {event["selected_use_case"]}</p>'
            )
        html_parts.append(render_image_meta(event.get("image_meta")))

    elif event_type == "clarification_required":
        html_parts.append("<p><strong>❓ Clarification Required:</strong></p>")
        questions = event.get("questions", [])
        html_parts.append(f"<p><strong>Number of Questions:</strong> {len(questions)}</p>")
        
        if questions:
            html_parts.append("<details><summary>View Questions</summary>")
            html_parts.append("<ul>")
            for q in questions:
                spec_name = q.get("spec_name", "unknown")
                question = q.get("question", "")
                hint = q.get("hint", "")
                options = q.get("options", [])
                confidence = q.get("confidence", 1.0)
                
                html_parts.append(f"<li><strong>{spec_name}</strong> (confidence: {confidence:.2f})")
                html_parts.append(f"<br/>Q: {escape_html(question)}")
                if hint:
                    html_parts.append(f"<br/>💡 {escape_html(hint)}")
                if options:
                    html_parts.append(f"<br/>Options: {', '.join(options)}")
                html_parts.append("</li>")
            html_parts.append("</ul>")
            html_parts.append("</details>")
        
        instructions_preview = event.get("instructions_preview", [])
        if instructions_preview:
            html_parts.append("<details><summary>Preview Instructions</summary>")
            html_parts.append("<ol>")
            for inst in instructions_preview:
                html_parts.append(f"<li>{escape_html(inst)}</li>")
            html_parts.append("</ol>")
            html_parts.append("</details>")

    elif event_type == "regex_inference":
        html_parts.append("<p><strong>🔍 Regex Inference:</strong></p>")
        html_parts.append("<ul>")
        html_parts.append(
            f'<li>Inferred Speed: <code>{event.get("inferred_speed", "None")}</code></li>'
        )
        html_parts.append(
            f'<li>Inferred Use Case: <code>{event.get("inferred_use_case", "None")}</code></li>'
        )
        html_parts.append(f'<li>Final Speed: <code>{event.get("final_speed", "None")}</code></li>')
        html_parts.append(
            f'<li>Final Use Case: <code>{event.get("final_use_case", "None")}</code></li>'
        )
        html_parts.append("</ul>")

    elif event_type in ["llm_call_clarification", "llm_call_recommendation", "llm_call_job_identification"]:
        stage_name = event_type.replace("llm_call_", "").title()
        html_parts.append(f"<p><strong>🤖 LLM Call ({stage_name}):</strong></p>")
        html_parts.append("<ul>")
        html_parts.append(f'<li>Model: <code>{event.get("model", "unknown")}</code></li>')
        if "missing_keys" in event:
            html_parts.append(f'<li>Missing Keys: <code>{event.get("missing_keys", [])}</code></li>')
        if "user_text" in event:
            html_parts.append(
                f'<li>User Text: <code>{escape_html(event.get("user_text", "")[:100])}</code></li>'
            )
        html_parts.append(render_image_meta(event.get("image_meta")))
        html_parts.append("</ul>")
        html_parts.append("<details><summary>View Prompt</summary>")
        prompt = escape_html(event.get("prompt", ""))
        html_parts.append(f"<pre>{prompt}</pre>")
        html_parts.append("</details>")

    elif event_type in [
        "llm_response_clarification",
        "llm_response_recommendation",
        "llm_response_job_identification",
    ]:
        stage_name = event_type.replace("llm_response_", "").title()
        html_parts.append(f"<p><strong>💬 LLM Response ({stage_name}):</strong></p>")
        html_parts.append("<ul>")
        html_parts.append(f'<li>Model: <code>{event.get("model", "unknown")}</code></li>')
        html_parts.append("</ul>")
        html_parts.append("<details><summary>View Response</summary>")
        response = escape_html(event.get("raw_response", ""))
        html_parts.append(f"<pre>{response}</pre>")
        html_parts.append("</details>")

    elif event_type == "llm_parse_error":
        html_parts.append("<p><strong>❌ LLM Parse Error:</strong></p>")
        html_parts.append("<ul>")
        html_parts.append(
            f'<li>Stage: <code>{escape_html(event.get("stage", "unknown"))}</code></li>'
        )
        html_parts.append(
            f'<li>Error: <code>{escape_html(event.get("error", "unknown"))}</code></li>'
        )
        html_parts.append(
            f'<li>Raw: <code>{escape_html(event.get("raw", "")[:200])}</code>...</li>'
        )
        html_parts.append("</ul>")

    elif event_type in ["llm_error", "job_identification_result", "candidate_selection"]:
        html_parts.append("<p><strong>❌ LLM Parse Error:</strong></p>")
        html_parts.append("<ul>")
        html_parts.append(
            f'<li>Error: <code>{escape_html(event.get("error", "unknown"))}</code></li>'
        )
        html_parts.append(
            f'<li>Raw: <code>{escape_html(event.get("raw", "")[:200])}</code>...</li>'
        )
        html_parts.append("</ul>")

    elif event_type == "recommendation_result":
        html_parts.append("<p><strong>✅ Recommendation Result:</strong></p>")
        html_parts.append("<ul>")
        html_parts.append(
            f'<li><strong>Diagnosis:</strong> {escape_html(event.get("diagnosis", "N/A")[:150])}</li>'
        )
        html_parts.append(
            f'<li><strong>Primary Products:</strong> {event.get("primary_products_count", 0)}</li>'
        )
        html_parts.append(f'<li><strong>Tools:</strong> {event.get("tools_count", 0)}</li>')
        html_parts.append(
            f'<li><strong>Optional Extras:</strong> {event.get("optional_extras_count", 0)}</li>'
        )
        html_parts.append("</ul>")
        
        final_instructions = event.get("final_instructions", [])
        if final_instructions:
            html_parts.append("<details><summary>View Final Instructions</summary>")
            html_parts.append("<ol>")
            for inst in final_instructions:
                html_parts.append(f"<li>{escape_html(inst)}</li>")
            html_parts.append("</ol>")
            html_parts.append("</details>")
        
        fit_values = event.get("fit_values", {})
        if fit_values:
            html_parts.append("<p><strong>Fit Values:</strong></p>")
            html_parts.append("<ul>")
            for key, value in fit_values.items():
                html_parts.append(f"<li><strong>{key}:</strong> {value}</li>")
            html_parts.append("</ul>")

    elif event_type == "user_selection":
        html_parts.append("<p><strong>🎯 User Selection:</strong></p>")
        if event.get("selected_speed"):
            html_parts.append(f'<p><strong>Selected Speed:</strong> {event["selected_speed"]}</p>')
        if event.get("selected_use_case"):
            html_parts.append(
                f'<p><strong>Selected Use Case:</strong> {event["selected_use_case"]}</p>'
            )
        html_parts.append(render_image_meta(event.get("image_meta")))

    else:
        # Generic handler
        html_parts.append("<p><strong>Event Data:</strong></p>")
        html_parts.append("<ul>")
        for key, value in event.items():
            if key not in ["event_type", "timestamp"]:
                value_str = str(value)[:200]
                html_parts.append(
                    f"<li><strong>{key}:</strong> <code>{escape_html(value_str)}</code></li>"
                )
        html_parts.append("</ul>")

    html_parts.append("</div></div>")
    return "\n".join(html_parts)


def group_events_by_session(events: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """Group events by user interaction sessions.

    A new session starts only with user_input events (when user enters a new problem).
    user_selection events (button clicks during clarification) are grouped with the current session.
    """
    sessions = []
    current_session = None

    for event in events:
        if event.get("event_type") == "user_input":
            # Start a new session only on fresh problem input
            current_session = {
                "start_time": event.get("timestamp"),
                "user_text": event.get("problem_text", ""),
                "events": [event],
            }
            sessions.append(current_session)
        elif current_session is not None:
            # Add all other events to current session (including user_selection)
            current_session["events"].append(event)

    return sessions


def create_html_log(log_file: Path) -> str:
    """Create an HTML representation of the log file grouped by sessions."""
    log_file_name = log_file.name
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Read and group events
    events = []
    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        event = json.loads(line)
                        events.append(event)
                    except json.JSONDecodeError:
                        pass

    sessions = group_events_by_session(events)

    # Build HTML with sessions
    session_html = ""
    for i, session in enumerate(sessions, 1):
        session_time = format_timestamp(session["start_time"])
        user_text = escape_html(session["user_text"][:80])
        if len(session["user_text"]) > 80:
            user_text += "..."

        session_html += f"""
        <div class="session">
            <div class="session-header">
                <div class="session-header-content">
                    <h2>Session {i}</h2>
                    <p><strong>Time:</strong> <span class="session-time">{session_time}</span></p>
                    <p><strong>User Input:</strong> <code>{user_text}</code></p>
                    <p><strong>Events:</strong> {len(session['events'])}</p>
                </div>
                <div class="session-toggle">▼</div>
            </div>
            <div class="session-events">
"""

        for event in session["events"]:
            session_html += format_event_html(event)

        session_html += """
            </div>
        </div>
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLM Interaction Log</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            padding: 2rem;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        header {{
            margin-bottom: 2rem;
            border-bottom: 2px solid #334155;
            padding-bottom: 1rem;
        }}

        h1 {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
            color: #60a5fa;
        }}

        .log-info {{
            display: flex;
            gap: 2rem;
            font-size: 0.9rem;
            color: #94a3b8;
            flex-wrap: wrap;
            margin-top: 0.5rem;
        }}

        .stats {{
            margin-top: 1rem;
            padding: 1rem;
            background: #1e293b;
            border-radius: 0.5rem;
            border-left: 3px solid #60a5fa;
        }}

        .stats p {{
            margin: 0.25rem 0;
            font-size: 0.95rem;
        }}

        .session {{
            margin-bottom: 2rem;
            border: 2px solid #475569;
            border-radius: 0.75rem;
            background: #0f172a;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }}

        .session-header {{
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            padding: 1.5rem;
            border-bottom: 2px solid #475569;
            cursor: pointer;
            user-select: none;
            transition: background 0.2s;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }}

        .session-header:hover {{
            background: linear-gradient(135deg, #334155 0%, #1e293b 100%);
        }}

        .session-header-content {{
            flex: 1;
        }}

        .session-header h2 {{
            font-size: 1.2rem;
            color: #60a5fa;
            margin: 0 0 0.5rem 0;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .session-header p {{
            color: #cbd5e1;
            margin: 0.25rem 0;
            font-size: 0.9rem;
        }}

        .session-time {{
            color: #94a3b8;
            font-size: 0.85rem;
        }}

        .session-toggle {{
            display: inline-block;
            transition: transform 0.3s;
            font-size: 1.5rem;
            color: #60a5fa;
            margin-left: 1rem;
        }}

        .session.collapsed .session-toggle {{
            transform: rotate(-90deg);
        }}

        .session-events {{
            padding: 1rem;
            max-height: 3000px;
            overflow: hidden;
            transition: max-height 0.3s ease-out, padding 0.3s;
        }}

        .session.collapsed .session-events {{
            max-height: 0;
            padding: 0 1rem;
        }}

        .event {{
            margin-bottom: 1rem;
            border: 1px solid #334155;
            border-radius: 0.5rem;
            background: #1e293b;
            overflow: hidden;
        }}

        .event:last-child {{
            margin-bottom: 0;
        }}

        .event-header {{
            background: #0f172a;
            padding: 0.75rem 1rem;
            border-bottom: 1px solid #334155;
            font-size: 0.9rem;
            color: #60a5fa;
            margin: 0;
            cursor: pointer;
            user-select: none;
            font-weight: 600;
        }}

        .event-content {{
            padding: 0.75rem 1rem;
            font-size: 0.9rem;
        }}

        .event-user_input .event-header {{ border-left: 4px solid #10b981; }}
        .event-user_selection .event-header {{ border-left: 4px solid #06b6d4; }}
        .event-clarification_required .event-header {{ border-left: 4px solid #f59e0b; }}
        .event-regex_inference .event-header {{ border-left: 4px solid #8b5cf6; }}
        .event-llm_call_clarification .event-header {{ border-left: 4px solid #3b82f6; }}
        .event-llm_response_clarification .event-header {{ border-left: 4px solid #3b82f6; }}
        .event-llm_call_job_identification .event-header {{ border-left: 4px solid #3b82f6; }}
        .event-llm_response_job_identification .event-header {{ border-left: 4px solid #3b82f6; }}
        .event-llm_call_recommendation .event-header {{ border-left: 4px solid #3b82f6; }}
        .event-llm_response_recommendation .event-header {{ border-left: 4px solid #3b82f6; }}
        .event-llm_inference_result .event-header {{ border-left: 4px solid #06b6d4; }}
        .event-llm_parse_error .event-header {{ border-left: 4px solid #ef4444; }}
        .event-recommendation_result .event-header {{ border-left: 4px solid #10b981; }}
        .event-job_identification_result .event-header {{ border-left: 4px solid #10b981; }}
        .event-candidate_selection .event-header {{ border-left: 4px solid #8b5cf6; }}

        .event-content p {{
            margin: 0.3rem 0;
        }}

        .event-content ul {{
            list-style: none;
            padding-left: 1.5rem;
            margin: 0.3rem 0;
        }}

        .event-content li {{
            margin: 0.2rem 0;
        }}

        code {{
            background: #0f172a;
            padding: 0.2rem 0.4rem;
            border-radius: 0.25rem;
            font-family: "Monaco", "Menlo", "Ubuntu Mono", monospace;
            font-size: 0.85em;
            color: #a8e6cf;
        }}

        pre {{
            background: #0f172a;
            padding: 0.75rem;
            border-radius: 0.5rem;
            overflow-x: auto;
            font-size: 0.8rem;
            margin: 0.3rem 0;
            border-left: 3px solid #334155;
            line-height: 1.4;
        }}

        details {{
            margin-top: 0.3rem;
            cursor: pointer;
        }}

        details summary {{
            color: #60a5fa;
            user-select: none;
            padding: 0.3rem 0.5rem;
            background: #0f172a;
            border-radius: 0.25rem;
            transition: background 0.2s;
            font-size: 0.85rem;
        }}

        details summary:hover {{
            background: #1e293b;
        }}

        details[open] summary {{
            margin-bottom: 0.3rem;
        }}

        .filter-controls {{
            margin-bottom: 2rem;
            padding: 1rem;
            background: #1e293b;
            border-radius: 0.5rem;
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
        }}

        .filter-controls label {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            cursor: pointer;
            font-size: 0.9rem;
        }}

        .filter-controls input[type="checkbox"] {{
            cursor: pointer;
        }}

        footer {{
            margin-top: 3rem;
            padding-top: 1rem;
            border-top: 2px solid #334155;
            font-size: 0.85rem;
            color: #64748b;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📋 LLM Interaction Log</h1>
            <div class="log-info">
                <div><strong>File:</strong> {log_file_name}</div>
                <div><strong>Generated:</strong> {current_time}</div>
            </div>
            <div class="stats">
                <p><strong>Sessions:</strong> {len(sessions)} | <strong>Total Events:</strong> {len(events)}</p>
            </div>
        </header>

        <div class="filter-controls">
            <label><input type="checkbox" class="filter" data-event-type="user_input" checked> User Input</label>
            <label><input type="checkbox" class="filter" data-event-type="clarification_required" checked> Clarification Required</label>
            <label><input type="checkbox" class="filter" data-event-type="llm_call_job_identification" checked> Job Identification Calls</label>
            <label><input type="checkbox" class="filter" data-event-type="llm_call_recommendation" checked> Recommendation Calls</label>
            <label><input type="checkbox" class="filter" data-event-type="recommendation_result" checked> Results</label>
            <label><input type="checkbox" class="filter" data-event-type="llm_parse_error" checked> Errors</label>
        </div>

        {session_html}

        <footer>
            <p>Generated on {current_time}</p>
        </footer>
    </div>

    <script>
        // Toggle session collapse
        document.querySelectorAll('.session-header').forEach(header => {{
            header.addEventListener('click', function() {{
                const session = this.closest('.session');
                session.classList.toggle('collapsed');
            }});
        }});

        // Filter functionality
        document.querySelectorAll('.filter').forEach(checkbox => {{
            checkbox.addEventListener('change', () => {{
                const eventType = checkbox.getAttribute('data-event-type');
                const events = document.querySelectorAll(`.event-${{eventType}}`);
                events.forEach(event => {{
                    event.style.display = checkbox.checked ? 'block' : 'none';
                }});
            }});
        }});
    </script>
</body>
</html>
"""

    return html


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        # Use provided log file
        log_file = Path(sys.argv[1])
    else:
        # Use today's log file (logs directory is in web/)
        today = datetime.now().strftime("%Y%m%d")
        log_file = Path(__file__).parent / f"logs/llm_interactions_{today}.jsonl"

    # Generate HTML
    html_content = create_html_log(log_file)

    # Write to temporary HTML file
    output_file = Path(__file__).parent / "logs" / "view_logs.html"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ Log viewer created: {output_file}")
    print("📖 Opening in browser...")

    # Open in browser
    webbrowser.open(f"file://{output_file.absolute()}")


def get_db_interactions(
    request_id: Optional[str] = None,
    event_type: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Query interactions from SQLite database."""
    if db_path is None:
        db_path = Path(__file__).parent.parent / "data" / "products.db"
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return []
    
    try:
        from error_logging import ErrorLogger
        logger = ErrorLogger(db_path=db_path)
        
        if request_id:
            return logger.get_interaction_trace(request_id)
        else:
            return logger.get_interactions(event_type=event_type, limit=1000)
    except Exception as e:
        print(f"❌ Error querying database: {e}")
        return []


def create_html_log_from_interactions(interactions: List[Dict[str, Any]]) -> str:
    """Create HTML view for database interactions."""
    if not interactions:
        return "<html><body><p>No interactions found.</p></body></html>"
    
    # Group by request_id if multiple requests
    requests = {}
    for interaction in interactions:
        req_id = interaction.get("request_id", "unknown")
        if req_id not in requests:
            requests[req_id] = []
        requests[req_id].append(interaction)
    
    html_parts = ["""
    <html>
    <head>
        <title>LLM Interactions - Database View</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .request { background: white; margin: 20px 0; padding: 15px; border-radius: 8px; }
            .request h2 { margin-top: 0; color: #333; }
            .interaction { margin: 10px 0; padding: 10px; background: #f9f9f9; border-left: 4px solid #0066cc; }
            .event-type { font-weight: bold; color: #0066cc; margin-right: 10px; }
            .timestamp { color: #666; font-size: 0.9em; }
            .data { margin-top: 5px; white-space: pre-wrap; font-family: monospace; font-size: 0.9em; }
            summary { cursor: pointer; font-weight: bold; }
            .summary { background: #e3f2fd; padding: 5px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <h1>LLM Interactions from Database</h1>
    """]
    
    for req_id, events in requests.items():
        html_parts.append(f"""
        <div class="request">
            <h2>Request: {escape_html(req_id)}</h2>
            <p><strong>Events:</strong> {len(events)}</p>
        """)
        
        for event in events:
            event_type = escape_html(str(event.get("event_type", "unknown")))
            timestamp = format_timestamp(str(event.get("timestamp", "")))
            data = event.get("data", {})
            
            # Parse JSON if string
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except (json.JSONDecodeError, ValueError):
                    pass
            
            data_str = json.dumps(data, indent=2) if data else "{}"
            
            html_parts.append(f"""
            <div class="interaction">
                <span class="event-type">{event_type}</span>
                <span class="timestamp">{timestamp}</span>
                <details>
                    <summary>Details</summary>
                    <div class="data">{escape_html(data_str)}</div>
                </details>
            </div>
            """)
        
        html_parts.append("</div>")
    
    html_parts.append("""
    </body>
    </html>
    """)
    
    return "".join(html_parts)


def main_db_mode(args: Any) -> None:
    """View interactions from database."""
    interactions = get_db_interactions(
        request_id=args.request,
        event_type=args.type,
        db_path=args.db_path,
    )
    
    if not interactions:
        print("❌ No interactions found")
        return
    
    print(f"✅ Found {len(interactions)} interaction(s)")
    
    # Generate HTML
    html_content = create_html_log_from_interactions(interactions)
    
    # Write to temporary HTML file
    output_file = Path(__file__).parent / "logs" / "view_logs_db.html"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"✅ Log viewer created: {output_file}")
    print("📖 Opening in browser...")
    
    webbrowser.open(f"file://{output_file.absolute()}")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="View LLM interaction logs (JSONL or database)"
    )
    parser.add_argument(
        "log_file",
        nargs="?",
        help="JSONL log file to view (use with local JSONL logs)"
    )
    parser.add_argument(
        "--db",
        choices=["sqlite"],
        help="Use database backend instead of JSONL"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        help="Path to SQLite database (default: data/products.db)"
    )
    parser.add_argument(
        "--request",
        type=str,
        help="Filter by request_id (for database mode)"
    )
    parser.add_argument(
        "--type",
        type=str,
        help="Filter by event_type (for database mode)"
    )
    
    args = parser.parse_args()
    
    if args.db == "sqlite":
        main_db_mode(args)
    else:
        # Use original JSONL mode
        if args.log_file:
            # Emulate passing the log file as a command-line argument to main()
            sys.argv = [sys.argv[0], str(args.log_file)]
        else:
            # No log file specified: emulate running with no extra CLI args
            sys.argv = [sys.argv[0]]
        main()

