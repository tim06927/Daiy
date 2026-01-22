"""Tests for error logging system.

Validates error logging to SQLite database, error types, recovery suggestions,
and CLI tool functionality.
"""

import json
import sqlite3
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from web.error_logging import (
    ErrorLogger,
    log_database_error,
    log_llm_error,
    log_processing_error,
    log_unexpected_error,
    log_validation_error,
)


class TestErrorLogger:
    """Test ErrorLogger class."""

    def test_init_creates_database(self):
        """ErrorLogger should create database and table."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            ErrorLogger(db_path=db_path)
            assert db_path.exists()

    def test_table_creation(self):
        """Should create error_log table with proper schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            logger = ErrorLogger(db_path=db_path)

            # Verify table exists
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='error_log'"
            )
            assert cursor.fetchone() is not None
            conn.close()

    def test_log_error(self):
        """Should log error to database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            logger = ErrorLogger(db_path=db_path)

            request_id = str(uuid.uuid4())
            logger.log_error(
                error_type="llm_error",
                error_message="Test error",
                request_id=request_id,
                operation="test_operation",
            )

            # Verify error was logged
            errors = logger.get_errors()
            assert len(errors) == 1
            assert errors[0]["error_type"] == "llm_error"
            assert errors[0]["error_message"] == "Test error"
            assert errors[0]["request_id"] == request_id

    def test_log_error_with_context(self):
        """Should store error context as JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            logger = ErrorLogger(db_path=db_path)

            context = {"model": "gpt-4-mini", "status_code": 429}
            logger.log_error(
                error_type="llm_error",
                error_message="Rate limited",
                context=context,
            )

            errors = logger.get_errors()
            assert len(errors) == 1
            stored_context = json.loads(errors[0]["context"])
            assert stored_context == context

    def test_get_errors_with_limit(self):
        """Should respect limit parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            logger = ErrorLogger(db_path=db_path)

            # Log 5 errors
            for i in range(5):
                logger.log_error(
                    error_type="validation_error",
                    error_message=f"Error {i}",
                )

            # Retrieve with limit
            errors = logger.get_errors(limit=3)
            assert len(errors) == 3

    def test_get_errors_with_offset(self):
        """Should support pagination with offset."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            logger = ErrorLogger(db_path=db_path)

            # Log 5 errors
            for i in range(5):
                logger.log_error(
                    error_type="validation_error",
                    error_message=f"Error {i}",
                )

            # Get first 2
            errors_page1 = logger.get_errors(limit=2, offset=0)
            assert len(errors_page1) == 2

            # Get next 2
            errors_page2 = logger.get_errors(limit=2, offset=2)
            assert len(errors_page2) == 2

            # Different content
            assert errors_page1[0]["id"] != errors_page2[0]["id"]

    def test_filter_by_request_id(self):
        """Should filter errors by request_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            logger = ErrorLogger(db_path=db_path)

            request_id_1 = str(uuid.uuid4())
            request_id_2 = str(uuid.uuid4())

            # Log errors with different request IDs
            logger.log_error("llm_error", "Error 1", request_id=request_id_1)
            logger.log_error("validation_error", "Error 2", request_id=request_id_2)

            # Filter by request_id_1
            errors = logger.get_errors(request_id=request_id_1)
            assert len(errors) == 1
            assert errors[0]["request_id"] == request_id_1

    def test_filter_by_error_type(self):
        """Should filter errors by error_type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            logger = ErrorLogger(db_path=db_path)

            # Log different error types
            logger.log_error("llm_error", "LLM error")
            logger.log_error("validation_error", "Validation error")
            logger.log_error("llm_error", "Another LLM error")

            # Filter by error type
            errors = logger.get_errors(error_type="llm_error")
            assert len(errors) == 2
            assert all(e["error_type"] == "llm_error" for e in errors)

    def test_get_error_summary(self):
        """Should return error summary with statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            logger = ErrorLogger(db_path=db_path)

            # Log different errors
            logger.log_error("llm_error", "Error 1")
            logger.log_error("validation_error", "Error 2")
            logger.log_error("llm_error", "Error 1")

            summary = logger.get_error_summary()
            assert summary["total_errors"] == 3
            assert summary["errors_by_type"]["llm_error"] == 2
            assert summary["errors_by_type"]["validation_error"] == 1
            assert summary["top_messages"] is not None

    def test_stack_trace_storage(self):
        """Should store stack traces for unexpected errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            logger = ErrorLogger(db_path=db_path)

            stack_trace = "File 'test.py', line 42, in test_func\n  raise ValueError('test')"
            logger.log_error(
                error_type="unexpected_error",
                error_message="Unexpected error",
                stack_trace=stack_trace,
            )

            errors = logger.get_errors()
            assert errors[0]["stack_trace"] == stack_trace

    def test_recovery_suggestion_storage(self):
        """Should store recovery suggestions for all errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            logger = ErrorLogger(db_path=db_path)

            recovery = "Wait 60 seconds and retry"
            logger.log_error(
                error_type="llm_error",
                error_message="Rate limited",
                recovery_suggestion=recovery,
            )

            errors = logger.get_errors()
            assert errors[0]["recovery_suggestion"] == recovery


class TestErrorLoggingHelpers:
    """Test error logging helper functions."""

    def test_log_llm_error(self):
        """log_llm_error should log with correct error type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with patch("web.error_logging._error_logger", ErrorLogger(db_path=db_path)):
                request_id = str(uuid.uuid4())
                log_llm_error(
                    "OpenAI rate limited",
                    request_id=request_id,
                    operation="llm_recommendation",
                )

                logger = ErrorLogger(db_path=db_path)
                errors = logger.get_errors()
                assert errors[0]["error_type"] == "llm_error"

    def test_log_validation_error(self):
        """log_validation_error should log with correct error type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with patch("web.error_logging._error_logger", ErrorLogger(db_path=db_path)):
                log_validation_error(
                    "Invalid problem_text",
                    operation="validate_input",
                )

                logger = ErrorLogger(db_path=db_path)
                errors = logger.get_errors()
                assert errors[0]["error_type"] == "validation_error"

    def test_log_database_error(self):
        """log_database_error should log with correct error type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with patch("web.error_logging._error_logger", ErrorLogger(db_path=db_path)):
                log_database_error(
                    "Query timeout",
                    operation="select_candidates",
                )

                logger = ErrorLogger(db_path=db_path)
                errors = logger.get_errors()
                assert errors[0]["error_type"] == "database_error"

    def test_log_processing_error(self):
        """log_processing_error should log with correct error type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with patch("web.error_logging._error_logger", ErrorLogger(db_path=db_path)):
                log_processing_error(
                    "Invalid image format",
                    operation="process_image",
                )

                logger = ErrorLogger(db_path=db_path)
                errors = logger.get_errors()
                assert errors[0]["error_type"] == "processing_error"

    def test_log_unexpected_error(self):
        """log_unexpected_error should log with correct error type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with patch("web.error_logging._error_logger", ErrorLogger(db_path=db_path)):
                log_unexpected_error(
                    "Uncaught exception",
                    operation="main_flow",
                    stack_trace="Traceback...",
                )

                logger = ErrorLogger(db_path=db_path)
                errors = logger.get_errors()
                assert errors[0]["error_type"] == "unexpected_error"


class TestErrorExport:
    """Test error export functionality."""

    def test_export_json(self):
        """Should export errors as JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            logger = ErrorLogger(db_path=db_path)

            logger.log_error("llm_error", "Test error", operation="test")
            logger.log_error("validation_error", "Validation error")

            export_file = Path(tmpdir) / "errors.json"
            logger.export_errors_json(str(export_file))

            assert export_file.exists()
            data = json.loads(export_file.read_text())
            assert len(data) == 2
            assert data[0]["error_type"] == "validation_error"  # Reverse order

    def test_export_jsonl(self):
        """Should export errors as JSONL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            logger = ErrorLogger(db_path=db_path)

            logger.log_error("llm_error", "Error 1")
            logger.log_error("validation_error", "Error 2")

            export_file = Path(tmpdir) / "errors.jsonl"
            logger.export_errors_jsonl(str(export_file))

            assert export_file.exists()
            lines = export_file.read_text().strip().split("\n")
            assert len(lines) == 2
            for line in lines:
                data = json.loads(line)
                assert "error_type" in data
                assert "error_message" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
