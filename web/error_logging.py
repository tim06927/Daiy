"""Comprehensive error logging with database persistence.

Stores all errors to SQLite database for persistent tracking across
Render deployments. Integrates with existing event logging system.

Error types captured:
- llm_error: OpenAI API errors, parsing failures
- validation_error: Invalid input, constraint violations
- database_error: Query failures, connection issues
- processing_error: Image processing, file operations
- unexpected_error: Uncaught exceptions with full stack trace

Each error logged with:
- timestamp, request_id, user context
- error type and message
- full stack trace
- operation context (which phase, what parameters)
- timing info (if available)
- recovery suggestion (if applicable)
"""

import json
import logging
import sqlite3
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

__all__ = [
    "ErrorLogger",
    "log_llm_error",
    "log_validation_error",
    "log_database_error",
    "log_processing_error",
    "log_unexpected_error",
    "log_interaction",
    "init_error_logging_db",
]

logger = logging.getLogger(__name__)


class ErrorLogger:
    """Log errors to SQLite database for persistent storage on Render."""

    def __init__(self, db_path: Optional[Union[Path, str]] = None):
        """Initialize error logger."""
        if db_path is None:
            db_path = Path(__file__).parent.parent / "data" / "products.db"
        
        self.db_path = db_path
        self._ensure_table_exists()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _ensure_table_exists(self) -> None:
        """Create error_log and interactions tables if they don't exist."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Create error_log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS error_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    request_id TEXT,
                    error_type TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    stack_trace TEXT,
                    context JSON,
                    operation TEXT,
                    phase TEXT,
                    user_input TEXT,
                    timing_data JSON,
                    recovery_suggestion TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create interactions table (for all events: user_input, llm_calls, recommendations, etc.)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    data JSON,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for error_log
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_error_timestamp
                ON error_log(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_error_request_id
                ON error_log(request_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_error_type
                ON error_log(error_type)
            """)
            
            # Create indexes for interactions
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_interaction_request_id
                ON interactions(request_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_interaction_event_type
                ON interactions(event_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_interaction_timestamp
                ON interactions(timestamp)
            """)
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
    
    def log_error(
        self,
        error_type: str,
        error_message: str,
        request_id: Optional[str] = None,
        operation: Optional[str] = None,
        phase: Optional[str] = None,
        user_input: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None,
        timing_data: Optional[Dict[str, Any]] = None,
        recovery_suggestion: Optional[str] = None,
    ) -> None:
        """Log error to database."""
        try:
            if stack_trace is None:
                stack_trace = traceback.format_exc() if sys.exc_info()[0] else None
            
            timestamp = datetime.now().isoformat()
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            context_json = json.dumps(context) if context else None
            timing_json = json.dumps(timing_data) if timing_data else None
            
            cursor.execute("""
                INSERT INTO error_log (
                    timestamp, request_id, error_type, error_message,
                    stack_trace, context, operation, phase, user_input,
                    timing_data, recovery_suggestion
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp, request_id, error_type, error_message,
                stack_trace, context_json, operation, phase, user_input,
                timing_json, recovery_suggestion
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Logged {error_type} for request {request_id}")
        except Exception as e:
            logger.error(f"Failed to log error to database: {e}")
    
    def get_errors(
        self,
        request_id: Optional[str] = None,
        error_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list:
        """Query errors from database."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = "SELECT * FROM error_log WHERE 1=1"
            params = []
            
            if request_id:
                query += " AND request_id = ?"
                params.append(request_id)
            
            if error_type:
                query += " AND error_type = ?"
                params.append(error_type)
            
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to query errors: {e}")
            return []
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get error summary statistics."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Total errors
            cursor.execute("SELECT COUNT(*) as count FROM error_log")
            total = cursor.fetchone()["count"]
            
            # Errors by type
            cursor.execute("""
                SELECT error_type, COUNT(*) as count
                FROM error_log
                GROUP BY error_type
                ORDER BY count DESC
            """)
            by_type = {row["error_type"]: row["count"] for row in cursor.fetchall()}
            
            # Recent errors (last 24 hours)
            cursor.execute("""
                SELECT COUNT(*) as count FROM error_log
                WHERE timestamp > datetime('now', '-1 day')
            """)
            recent = cursor.fetchone()["count"]
            
            # Most common error messages
            cursor.execute("""
                SELECT error_message, COUNT(*) as count
                FROM error_log
                GROUP BY error_message
                ORDER BY count DESC
                LIMIT 10
            """)
            top_messages = [
                {"message": row["error_message"], "count": row["count"]}
                for row in cursor.fetchall()
            ]
            
            conn.close()
            
            return {
                "total_errors": total,
                "errors_by_type": by_type,
                "errors_24h": recent,
                "top_messages": top_messages,
            }
        except Exception as e:
            logger.error(f"Failed to get error summary: {e}")
            return {}
    
    def export_errors_json(self, output_file: Union[Path, str]) -> None:
        """Export all errors to JSON file."""
        try:
            output_path = Path(output_file)
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM error_log ORDER BY timestamp DESC")
            rows = cursor.fetchall()
            conn.close()
            
            errors = []
            for row in rows:
                error = dict(row)
                # Parse JSON fields
                if error.get("context"):
                    error["context"] = json.loads(error["context"])
                if error.get("timing_data"):
                    error["timing_data"] = json.loads(error["timing_data"])
                errors.append(error)
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(errors, f, indent=2, default=str)
            
            logger.info(f"Exported {len(errors)} errors to {output_path}")
        except Exception as e:
            logger.error(f"Failed to export errors: {e}")
    
    def export_errors_jsonl(self, output_file: Union[Path, str]) -> None:
        """Export all errors to JSONL file."""
        try:
            output_path = Path(output_file)
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM error_log ORDER BY timestamp DESC")
            rows = cursor.fetchall()
            conn.close()
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                for row in rows:
                    error = dict(row)
                    # Parse JSON fields
                    if error.get("context"):
                        error["context"] = json.loads(error["context"])
                    if error.get("timing_data"):
                        error["timing_data"] = json.loads(error["timing_data"])
                    f.write(json.dumps(error, default=str) + "\n")
            
            logger.info(f"Exported errors to {output_path}")
        except Exception as e:
            logger.error(f"Failed to export errors: {e}")
    
    def log_interaction(
        self,
        event_type: str,
        request_id: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log an interaction event (user_input, llm_call, recommendation, etc.) to database."""
        try:
            timestamp = datetime.now().isoformat()
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            data_json = json.dumps(data) if data else None
            
            cursor.execute("""
                INSERT INTO interactions (
                    timestamp, request_id, event_type, data
                ) VALUES (?, ?, ?, ?)
            """, (
                timestamp, request_id, event_type, data_json
            ))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Logged interaction {event_type} for request {request_id}")
        except Exception as e:
            logger.error(f"Failed to log interaction: {e}")
    
    def get_interactions(
        self,
        request_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list:
        """Query interactions from database."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = "SELECT * FROM interactions WHERE 1=1"
            params = []
            
            if request_id:
                query += " AND request_id = ?"
                params.append(request_id)
            
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)
            
            query += " ORDER BY timestamp ASC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to query interactions: {e}")
            return []
    
    def get_interaction_trace(self, request_id: str) -> list:
        """Get all interactions (events) for a specific request in chronological order."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM interactions
                WHERE request_id = ?
                ORDER BY timestamp ASC
            """, (request_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            trace = []
            for row in rows:
                event = dict(row)
                # Parse JSON data field
                if event.get("data"):
                    try:
                        event["data"] = json.loads(event["data"])
                    except (json.JSONDecodeError, TypeError, ValueError):
                        # Ignore JSON parsing issues; keep original data representation.
                        pass
                trace.append(event)
            
            return trace
        except Exception as e:
            logger.error(f"Failed to get interaction trace: {e}")
            return []
    
    def get_interaction_summary(self) -> Dict[str, Any]:
        """Get interaction summary statistics."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Total interactions
            cursor.execute("SELECT COUNT(*) as count FROM interactions")
            total = cursor.fetchone()["count"]
            
            # Interactions by type
            cursor.execute("""
                SELECT event_type, COUNT(*) as count
                FROM interactions
                GROUP BY event_type
                ORDER BY count DESC
            """)
            by_type = {row["event_type"]: row["count"] for row in cursor.fetchall()}
            
            # Unique requests
            cursor.execute("""
                SELECT COUNT(DISTINCT request_id) as count FROM interactions
            """)
            unique_requests = cursor.fetchone()["count"]
            
            # Recent interactions (last 24 hours)
            cursor.execute("""
                SELECT COUNT(*) as count FROM interactions
                WHERE timestamp > datetime('now', '-1 day')
            """)
            recent = cursor.fetchone()["count"]
            
            conn.close()
            
            return {
                "total_interactions": total,
                "interactions_by_type": by_type,
                "unique_requests": unique_requests,
                "interactions_24h": recent,
            }
        except Exception as e:
            logger.error(f"Failed to get interaction summary: {e}")
            return {}


# Global error logger instance
_error_logger: Optional[ErrorLogger] = None


def _get_error_logger() -> ErrorLogger:
    """Get or create error logger."""
    global _error_logger
    if _error_logger is None:
        _error_logger = ErrorLogger()
    return _error_logger


def init_error_logging_db(db_path: Optional[Union[Path, str]] = None) -> None:
    """Initialize error logging database."""
    global _error_logger
    _error_logger = ErrorLogger(db_path)


def log_llm_error(
    error_message: str,
    request_id: Optional[str] = None,
    phase: Optional[str] = None,
    operation: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    recovery_suggestion: Optional[str] = None,
) -> None:
    """Log OpenAI API error or LLM processing failure."""
    _get_error_logger().log_error(
        error_type="llm_error",
        error_message=error_message,
        request_id=request_id,
        phase=phase,
        operation=operation,
        context=context,
        recovery_suggestion=recovery_suggestion or "Check OpenAI API status and quota",
    )


def log_validation_error(
    error_message: str,
    request_id: Optional[str] = None,
    operation: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    recovery_suggestion: Optional[str] = None,
) -> None:
    """Log validation error (invalid input, constraint violation)."""
    _get_error_logger().log_error(
        error_type="validation_error",
        error_message=error_message,
        request_id=request_id,
        operation=operation,
        context=context,
        recovery_suggestion=recovery_suggestion or "Check input format and try again",
    )


def log_database_error(
    error_message: str,
    request_id: Optional[str] = None,
    operation: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    recovery_suggestion: Optional[str] = None,
) -> None:
    """Log database query error."""
    _get_error_logger().log_error(
        error_type="database_error",
        error_message=error_message,
        request_id=request_id,
        operation=operation,
        context=context,
        recovery_suggestion=recovery_suggestion or "Database connection issue - try again",
    )


def log_processing_error(
    error_message: str,
    request_id: Optional[str] = None,
    operation: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    recovery_suggestion: Optional[str] = None,
) -> None:
    """Log image processing or file operation error."""
    _get_error_logger().log_error(
        error_type="processing_error",
        error_message=error_message,
        request_id=request_id,
        operation=operation,
        context=context,
        recovery_suggestion=recovery_suggestion or "Try uploading a different image",
    )


def log_unexpected_error(
    error_message: str,
    request_id: Optional[str] = None,
    operation: Optional[str] = None,
    phase: Optional[str] = None,
    user_input: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    stack_trace: Optional[str] = None,
) -> None:
    """Log unexpected error with full context and stack trace."""
    _get_error_logger().log_error(
        error_type="unexpected_error",
        error_message=error_message,
        request_id=request_id,
        operation=operation,
        phase=phase,
        user_input=user_input,
        context=context,
        stack_trace=stack_trace,
        recovery_suggestion="Report this issue to developers with the request ID",
    )


def log_interaction(
    event_type: str,
    request_id: str,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """Log an interaction event (user_input, llm_call, recommendation, etc.).
    
    Args:
        event_type: Type of event (user_input, llm_call_phase_1, llm_response_phase_1, etc.)
        request_id: UUID for correlating all events in a request
        data: Event-specific data (dict or any JSON-serializable object)
    """
    _get_error_logger().log_interaction(event_type, request_id, data)
