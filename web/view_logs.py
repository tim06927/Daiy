#!/usr/bin/env python3
"""View LLM interaction logs in a readable HTML format.

Usage:
    python view_logs.py                    # View today's log
    python view_logs.py logs/llm_*.jsonl   # View specific log file
"""

import json
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


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
        if event.get("selected_speed"):
            html_parts.append(f'<p><strong>Selected Speed:</strong> {event["selected_speed"]}</p>')
        if event.get("selected_use_case"):
            html_parts.append(
                f'<p><strong>Selected Use Case:</strong> {event["selected_use_case"]}</p>'
            )

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

    elif event_type == "llm_call_clarification":
        html_parts.append("<p><strong>🤖 LLM Call (Clarification):</strong></p>")
        html_parts.append("<ul>")
        html_parts.append(f'<li>Model: <code>{event.get("model", "unknown")}</code></li>')
        html_parts.append(f'<li>Missing Keys: <code>{event.get("missing_keys", [])}</code></li>')
        html_parts.append("</ul>")
        html_parts.append("<details><summary>View Prompt</summary>")
        prompt = escape_html(event.get("prompt", ""))
        html_parts.append(f"<pre>{prompt}</pre>")
        html_parts.append("</details>")

    elif event_type == "llm_response_clarification":
        html_parts.append("<p><strong>💬 LLM Response (Clarification):</strong></p>")
        html_parts.append("<ul>")
        html_parts.append(f'<li>Model: <code>{event.get("model", "unknown")}</code></li>')
        html_parts.append("</ul>")
        html_parts.append("<details><summary>View Response</summary>")
        response = escape_html(event.get("raw_response", ""))
        html_parts.append(f"<pre>{response}</pre>")
        html_parts.append("</details>")

    elif event_type == "llm_inference_result":
        html_parts.append("<p><strong>✅ LLM Inference Result:</strong></p>")
        html_parts.append("<ul>")
        html_parts.append(
            f'<li>Inferred Speed: <code>{event.get("inferred_speed", "None")}</code></li>'
        )
        html_parts.append(
            f'<li>Inferred Use Case: <code>{event.get("inferred_use_case", "None")}</code></li>'
        )
        html_parts.append(f'<li>Speed Options: <code>{event.get("speed_options", [])}</code></li>')
        html_parts.append(
            f'<li>Use Case Options: <code>{event.get("use_case_options", [])}</code></li>'
        )
        html_parts.append("</ul>")

    elif event_type == "llm_call_recommendation":
        html_parts.append("<p><strong>🤖 LLM Call (Recommendation):</strong></p>")
        html_parts.append("<ul>")
        html_parts.append(f'<li>Model: <code>{event.get("model", "unknown")}</code></li>')
        html_parts.append("</ul>")
        html_parts.append("<details><summary>View Prompt</summary>")
        prompt = escape_html(event.get("prompt", ""))
        html_parts.append(f"<pre>{prompt}</pre>")
        html_parts.append("</details>")

    elif event_type == "llm_response_recommendation":
        html_parts.append("<p><strong>💬 LLM Response (Recommendation):</strong></p>")
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
            f'<li>Error: <code>{escape_html(event.get("error", "unknown"))}</code></li>'
        )
        html_parts.append(
            f'<li>Raw: <code>{escape_html(event.get("raw", "")[:200])}</code>...</li>'
        )
        html_parts.append("</ul>")

    elif event_type == "user_selection":
        html_parts.append("<p><strong>🎯 User Selection:</strong></p>")
        if event.get("selected_speed"):
            html_parts.append(f'<p><strong>Selected Speed:</strong> {event["selected_speed"]}</p>')
        if event.get("selected_use_case"):
            html_parts.append(
                f'<p><strong>Selected Use Case:</strong> {event["selected_use_case"]}</p>'
            )

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
        .event-regex_inference .event-header {{ border-left: 4px solid #8b5cf6; }}
        .event-llm_call_clarification .event-header {{ border-left: 4px solid #f59e0b; }}
        .event-llm_response_clarification .event-header {{ border-left: 4px solid #f59e0b; }}
        .event-llm_inference_result .event-header {{ border-left: 4px solid #06b6d4; }}
        .event-llm_call_recommendation .event-header {{ border-left: 4px solid #f59e0b; }}
        .event-llm_response_recommendation .event-header {{ border-left: 4px solid #f59e0b; }}
        .event-llm_parse_error .event-header {{ border-left: 4px solid #ef4444; }}

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
            <label><input type="checkbox" class="filter" data-event-type="user_selection" checked> User Selection</label>
            <label><input type="checkbox" class="filter" data-event-type="regex_inference" checked> Regex Inference</label>
            <label><input type="checkbox" class="filter" data-event-type="llm_call_clarification" checked> LLM Calls</label>
            <label><input type="checkbox" class="filter" data-event-type="llm_inference_result" checked> Inference Results</label>
            <label><input type="checkbox" class="filter" data-event-type="llm_call_recommendation" checked> Recommendations</label>
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


if __name__ == "__main__":
    main()
