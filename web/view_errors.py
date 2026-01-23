#!/usr/bin/env python3
"""Error log viewer and exporter for Daiy deployment.

Access comprehensive error tracking from your Render deployment.

Usage:
    python view_errors.py                    # Show error summary
    python view_errors.py --all              # List all errors
    python view_errors.py --request abc123   # Errors for specific request
    python view_errors.py --type llm_error   # Errors of specific type
    python view_errors.py --export json      # Export as JSON
    python view_errors.py --export jsonl     # Export as JSONL
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).parent))
    from error_logging import ErrorLogger
else:
    from .error_logging import ErrorLogger


def format_timestamp(iso_string: str) -> str:
    """Format ISO timestamp to readable string."""
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, AttributeError):
        return iso_string


def print_error(error: Dict[str, Any]) -> None:
    """Pretty print a single error."""
    print(f"\n{'='*70}")
    print(f"Error ID: {error.get('id', 'N/A')}")
    print(f"Type: {error.get('error_type', 'unknown').upper()}")
    print(f"Time: {format_timestamp(error.get('timestamp', ''))}")
    
    if error.get("request_id"):
        print(f"Request ID: {error['request_id']}")
    
    print(f"\nMessage:")
    print(f"  {error.get('error_message', 'N/A')}")
    
    if error.get("operation"):
        print(f"\nOperation: {error['operation']}")
    
    if error.get("phase"):
        print(f"Phase: {error['phase']}")
    
    if error.get("recovery_suggestion"):
        print(f"\nRecovery: {error['recovery_suggestion']}")
    
    if error.get("user_input"):
        user_input = error["user_input"][:100]
        if len(error["user_input"]) > 100:
            user_input += "..."
        print(f"\nUser Input: {user_input}")
    
    if error.get("stack_trace"):
        print(f"\nStack Trace:")
        for line in error["stack_trace"].split("\n")[-10:]:
            if line.strip():
                print(f"  {line}")
    
    if error.get("context"):
        print(f"\nContext:")
        if isinstance(error["context"], str):
            try:
                context = json.loads(error["context"])
            except (json.JSONDecodeError, ValueError):
                # If parsing fails, wrap the raw string so it can still be displayed
                context = {"raw": error["context"]}
        else:
            context = error["context"]
        
        if isinstance(context, dict):
            for key, value in context.items():
                if isinstance(value, (dict, list)):
                    print(f"  {key}: {json.dumps(value)[:100]}")
                else:
                    print(f"  {key}: {str(value)[:100]}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="View and export error logs from Daiy deployment"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(__file__).parent.parent / "data" / "products.db",
        help="Path to database file"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Show all errors (with pagination)"
    )
    parser.add_argument(
        "--request",
        type=str,
        help="Filter errors by request ID"
    )
    parser.add_argument(
        "--type",
        type=str,
        help="Filter errors by type (llm_error, validation_error, etc.)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max errors to display (default: 20)"
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Pagination offset (default: 0)"
    )
    parser.add_argument(
        "--export",
        type=str,
        choices=["json", "jsonl"],
        help="Export errors to file (json or jsonl)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file for export"
    )
    
    args = parser.parse_args()
    
    # Initialize logger
    error_logger = ErrorLogger(args.db)
    
    # Handle export
    if args.export:
        if not args.output:
            args.output = Path(f"errors_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{args.export}")
        
        if args.export == "json":
            error_logger.export_errors_json(args.output)
        else:
            error_logger.export_errors_jsonl(args.output)
        
        print(f"\n✅ Exported to {args.output}")
        return
    
    # Show summary
    print("\n" + "="*70)
    print("ERROR SUMMARY")
    print("="*70)
    
    summary = error_logger.get_error_summary()
    print(f"\nTotal Errors: {summary.get('total_errors', 0)}")
    print(f"Errors (24h): {summary.get('errors_24h', 0)}")
    
    if summary.get("errors_by_type"):
        print("\nErrors by Type:")
        for error_type, count in summary["errors_by_type"].items():
            print(f"  {error_type}: {count}")
    
    if summary.get("top_messages"):
        print("\nTop Error Messages:")
        for item in summary["top_messages"][:5]:
            msg = item["message"][:60]
            if len(item["message"]) > 60:
                msg += "..."
            print(f"  {item['count']:3d}x {msg}")
    
    # Show errors
    print("\n" + "="*70)
    print("RECENT ERRORS")
    print("="*70)
    
    errors = error_logger.get_errors(
        request_id=args.request,
        error_type=args.type,
        limit=args.limit,
        offset=args.offset,
    )
    
    if not errors:
        print("\n✅ No errors found!")
        return
    
    print(f"\nShowing {len(errors)} error(s)")
    
    for error in errors:
        print_error(error)
    
    if args.all and len(errors) == args.limit:
        print(f"\n(Run with --offset {args.offset + args.limit} to see more)")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    main()
