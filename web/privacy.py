"""Privacy and consent module for GDPR-friendly alpha tracking.

This module provides:
- Text redaction for personal data (emails, phone numbers)
- Consent-aware logging (log_event)
- Data retention purge (90 days)
- Database schema migration for logs table
"""

import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

__all__ = [
    "redact_text",
    "log_event",
    "purge_old_logs",
    "ensure_logs_schema",
    "run_startup_purge",
    "PURGE_DAYS",
]

logger = logging.getLogger(__name__)

# Retention period in days
PURGE_DAYS = 90

# Path to track last purge timestamp
_PURGE_MARKER_FILE = Path(__file__).parent.parent / "data" / ".last_purge"

# Default database path
_DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "products.db"

# Regex patterns for redaction
_EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

# Phone pattern: matches common formats while avoiding false positives
# Intended to match:
#   - International: +49 123 456 7890, +1-555-123-4567
#   - US/EU: (555) 123-4567, 030-12345678, 555.123.4567
#   - Simple: 1234567890 (10+ consecutive digits)
# Avoids matching:
#   - Short numbers like quantities (11 gears, 12 speeds)
#   - Model numbers that don't look like phones
# Note: This is a best-effort pattern; some edge cases may not be caught.
# See test_privacy.py for tested formats.
_PHONE_PATTERN = re.compile(
    r"(?<![0-9])"  # Not preceded by a digit
    r"(?:\+?[0-9]{1,3}[-.\s]?)?"  # Optional country code
    r"(?:\(?\d{2,4}\)?[-.\s]?)?"  # Optional area code
    r"\d{3,4}[-.\s]?\d{3,4}"  # Main number (at least 6-8 digits)
    r"(?![0-9])"  # Not followed by a digit
)


def redact_text(text: str) -> str:
    """Redact sensitive patterns from text.

    Replaces:
    - Email addresses with [REDACTED_EMAIL]
    - Phone-like patterns with [REDACTED_PHONE]

    Args:
        text: Input text to redact.

    Returns:
        Text with sensitive patterns replaced.
    """
    if not text or not isinstance(text, str):
        return text

    # Redact emails first
    result = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)

    # Redact phone numbers
    result = _PHONE_PATTERN.sub("[REDACTED_PHONE]", result)

    return result


def _redact_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively redact sensitive data in a payload dict.

    Args:
        payload: Dict to redact.

    Returns:
        Redacted copy of the dict.
    """
    if not isinstance(payload, dict):
        return payload

    redacted = {}
    for key, value in payload.items():
        if isinstance(value, str):
            redacted[key] = redact_text(value)
        elif isinstance(value, dict):
            redacted[key] = _redact_payload(value)
        elif isinstance(value, list):
            redacted[key] = [
                _redact_payload(item) if isinstance(item, dict)
                else redact_text(item) if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            redacted[key] = value
    return redacted


def _get_db_path() -> Path:
    """Get database path from environment or default."""
    db_path = os.getenv("DB_PATH")
    if db_path:
        return Path(db_path)
    return _DEFAULT_DB_PATH


def _get_connection() -> sqlite3.Connection:
    """Get database connection."""
    db_path = _get_db_path()
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_logs_schema() -> None:
    """Ensure logs table exists with required columns.

    Creates or migrates the logs table to have:
    - id INTEGER PRIMARY KEY
    - created_at TEXT (UTC ISO)
    - event_type TEXT
    - payload_json TEXT
    - consent_ts TEXT
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        # Check if logs table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='logs'"
        )
        table_exists = cursor.fetchone() is not None

        if not table_exists:
            # Create new logs table
            cursor.execute("""
                CREATE TABLE logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT,
                    consent_ts TEXT
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs(created_at)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_logs_event_type ON logs(event_type)"
            )
            logger.info("Created logs table with new schema")
        else:
            # Migrate existing table: add missing columns
            cursor.execute("PRAGMA table_info(logs)")
            existing_columns = {row[1] for row in cursor.fetchall()}

            # These column definitions are hardcoded and safe
            # Using an allowlist pattern to prevent SQL injection
            ALLOWED_COLUMNS = {
                "created_at": "TEXT",
                "event_type": "TEXT",
                "payload_json": "TEXT",
                "consent_ts": "TEXT",
            }

            for col_name, col_type in ALLOWED_COLUMNS.items():
                if col_name not in existing_columns:
                    # Column names are validated against allowlist above
                    cursor.execute(f"ALTER TABLE logs ADD COLUMN {col_name} {col_type}")
                    logger.info(f"Added column {col_name} to logs table")

            # Create indexes if they don't exist
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs(created_at)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_logs_event_type ON logs(event_type)"
            )

        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to ensure logs schema: {e}")


def log_event(
    event_type: str,
    payload: Optional[Dict[str, Any]] = None,
    consent_ts: Optional[str] = None,
    session: Optional[Dict[str, Any]] = None,
) -> bool:
    """Log an event to the database with consent check and redaction.

    This is the single entry point for all tracking writes.

    Args:
        event_type: Type of event (user_input, llm_prompt, llm_response, etc.)
        payload: Event data to store (will be redacted and JSON-encoded)
        consent_ts: Consent timestamp from session (optional if session provided)
        session: Flask session dict (used to check consent if consent_ts not provided)

    Returns:
        True if event was logged, False if not (no consent or error)
    """
    # Check consent
    if session is not None:
        if not session.get("alpha_consent"):
            logger.debug("log_event skipped: no consent in session")
            return False
        consent_ts = consent_ts or session.get("alpha_consent_ts")
    elif consent_ts is None:
        # No consent info provided at all - don't log
        logger.debug("log_event skipped: no consent_ts provided")
        return False

    try:
        # Redact payload
        redacted_payload = _redact_payload(payload) if payload else {}

        # Serialize to JSON
        payload_json = json.dumps(redacted_payload, ensure_ascii=False, default=str)

        # Get current UTC timestamp
        created_at = datetime.now(timezone.utc).isoformat()

        # Write to database
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO logs (created_at, event_type, payload_json, consent_ts)
            VALUES (?, ?, ?, ?)
            """,
            (created_at, event_type, payload_json, consent_ts),
        )

        conn.commit()
        conn.close()

        logger.debug(f"Logged event: {event_type}")
        return True

    except Exception as e:
        logger.error(f"Failed to log event {event_type}: {e}")
        return False


def purge_old_logs(days: int = PURGE_DAYS) -> int:
    """Delete log records older than the specified number of days.

    Also deletes associated photo files if stored as file paths.

    Args:
        days: Number of days to retain (default: 90)

    Returns:
        Number of records deleted.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff.isoformat()

        conn = _get_connection()
        cursor = conn.cursor()

        # First, find records to delete and check for photo paths
        cursor.execute(
            "SELECT id, payload_json FROM logs WHERE created_at < ?",
            (cutoff_str,),
        )
        rows = cursor.fetchall()

        # Delete associated photo files
        uploads_dir = Path(__file__).parent / "uploads"
        deleted_files = 0
        for row in rows:
            try:
                payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
                # Check for stored photo paths in various payload formats
                photo_path = payload.get("photo_path") or payload.get("image_path")
                if photo_path:
                    full_path = uploads_dir / Path(photo_path).name
                    if full_path.exists() and full_path.is_file():
                        full_path.unlink()
                        deleted_files += 1
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Error processing old log record {row['id']}: {e}")

        # Delete old records
        cursor.execute("DELETE FROM logs WHERE created_at < ?", (cutoff_str,))
        deleted_count = cursor.rowcount

        conn.commit()
        conn.close()

        logger.info(
            f"Purged {deleted_count} log records older than {days} days "
            f"(deleted {deleted_files} photo files)"
        )
        return deleted_count

    except Exception as e:
        logger.error(f"Failed to purge old logs: {e}")
        return 0


def _should_run_daily_purge() -> bool:
    """Check if we should run the daily purge.

    Returns True if no purge has run today.
    """
    try:
        if not _PURGE_MARKER_FILE.exists():
            return True

        last_purge_str = _PURGE_MARKER_FILE.read_text().strip()
        last_purge = datetime.fromisoformat(last_purge_str)

        # Check if last purge was more than 24 hours ago
        now = datetime.now(timezone.utc)
        return (now - last_purge) > timedelta(hours=24)

    except Exception:
        return True


def _mark_purge_done() -> None:
    """Mark that purge has been completed."""
    try:
        _PURGE_MARKER_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PURGE_MARKER_FILE.write_text(datetime.now(timezone.utc).isoformat())
    except Exception as e:
        logger.warning(f"Failed to write purge marker: {e}")


def run_startup_purge() -> None:
    """Run purge at app startup and set up daily lazy trigger.

    This should be called once when the Flask app starts.
    """
    # Ensure schema exists
    ensure_logs_schema()

    # Run purge if needed
    if _should_run_daily_purge():
        purge_old_logs()
        _mark_purge_done()


def run_lazy_purge() -> None:
    """Run purge lazily on first request of the day.

    Call this from a before_request handler.
    """
    if _should_run_daily_purge():
        purge_old_logs()
        _mark_purge_done()
