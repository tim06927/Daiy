"""Logging configuration for the scraper.

Provides structured logging with both console and file output.
Consistent with the app's JSONL logging approach for LLM interactions.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

__all__ = [
    "setup_logging",
    "get_logger",
    "log_scrape_event",
    "LOG_DIR",
]

# Log directory (same pattern as web app)
LOG_DIR = Path(__file__).parent.parent / "logs"


class JSONLFileHandler(logging.Handler):
    """Custom handler that writes structured JSONL logs."""

    def __init__(self, log_dir: Path, prefix: str = "scrape"):
        super().__init__()
        self.log_dir = log_dir
        self.log_dir.mkdir(exist_ok=True)
        self.prefix = prefix
        self._current_date: Optional[str] = None
        self._file_handle = None

    def _get_log_file(self) -> Path:
        """Get log file path, rotating daily."""
        today = datetime.now().strftime("%Y%m%d")
        if today != self._current_date:
            self._current_date = today
            if self._file_handle:
                self._file_handle.close()
            self._file_handle = None
        return self.log_dir / f"{self.prefix}_{today}.jsonl"

    def emit(self, record: logging.LogRecord) -> None:
        try:
            log_file = self._get_log_file()
            
            # Build structured log entry
            entry = {
                "timestamp": datetime.now().isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            
            # Add extra fields if present
            if hasattr(record, "event_type"):
                entry["event_type"] = record.event_type
            if hasattr(record, "extra_data"):
                entry.update(record.extra_data)
            
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        if self._file_handle:
            self._file_handle.close()
        super().close()


class ColoredConsoleHandler(logging.StreamHandler):
    """Console handler with colored output for better readability."""

    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # Only colorize if output is a terminal
            if hasattr(self.stream, "isatty") and self.stream.isatty():
                color = self.COLORS.get(record.levelname, "")
                record.levelname = f"{color}{record.levelname}{self.RESET}"
            super().emit(record)
        except Exception:
            self.handleError(record)


def setup_logging(
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = True,
    log_dir: Optional[Path] = None,
) -> logging.Logger:
    """Set up logging for the scraper.

    Args:
        level: Logging level (default: INFO)
        log_to_file: Whether to log to JSONL file
        log_to_console: Whether to log to console
        log_dir: Custom log directory (default: project logs/)

    Returns:
        Configured root logger for scrape module
    """
    # Get the scrape logger
    logger = logging.getLogger("scrape")
    logger.setLevel(level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler
    if log_to_console:
        console_handler = ColoredConsoleHandler(sys.stdout)
        console_handler.setLevel(level)
        console_format = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)
    
    # File handler (JSONL)
    if log_to_file:
        file_handler = JSONLFileHandler(log_dir or LOG_DIR)
        file_handler.setLevel(logging.DEBUG)  # Capture all levels to file
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "scrape") -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name (will be prefixed with 'scrape.')

    Returns:
        Logger instance
    """
    if name == "scrape":
        return logging.getLogger("scrape")
    return logging.getLogger(f"scrape.{name}")


def log_scrape_event(
    event_type: str,
    data: Dict[str, Any],
    level: int = logging.INFO,
    logger_name: str = "scrape",
) -> None:
    """Log a structured scrape event.

    Args:
        event_type: Type of event (e.g., 'page_fetch', 'product_parse', 'error')
        data: Event-specific data
        level: Log level
        logger_name: Logger to use
    """
    logger = get_logger(logger_name)
    
    # Create a LogRecord with extra data
    record = logger.makeRecord(
        logger.name,
        level,
        "(scrape)",
        0,
        data.get("message", event_type),
        (),
        None,
    )
    record.event_type = event_type
    record.extra_data = {k: v for k, v in data.items() if k != "message"}
    
    logger.handle(record)
