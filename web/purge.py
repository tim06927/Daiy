#!/usr/bin/env python3
"""Standalone script to purge old log records.

Run this daily via cron or Render scheduled job:
    python purge.py

This script:
1. Deletes log records older than 90 days
2. Removes associated photo files if stored separately
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from privacy import PURGE_DAYS, ensure_logs_schema, purge_old_logs


def main() -> int:
    """Run the purge operation."""
    print(f"Starting log purge (retention: {PURGE_DAYS} days)...")

    # Ensure schema exists
    ensure_logs_schema()

    # Run purge
    deleted = purge_old_logs()

    print(f"Purge complete: {deleted} records deleted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
