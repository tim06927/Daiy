"""Logging utilities for the Daiy web app.

Provides structured JSONL logging for LLM interactions and other events.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

__all__ = ["log_interaction", "LOG_DIR", "LOG_FILE"]

# Setup LLM interaction logging
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"llm_interactions_{datetime.now().strftime('%Y%m%d')}.jsonl"


def log_interaction(event_type: str, data: Dict[str, Any]) -> None:
    """Log LLM interactions to a structured JSONL file.

    Args:
        event_type: Type of event (user_input, regex_inference, llm_call, llm_response, etc.)
        data: Event-specific data to log
    """
    log_entry = {"timestamp": datetime.now().isoformat(), "event_type": event_type, **data}
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
