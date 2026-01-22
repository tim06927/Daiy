#!/usr/bin/env python3
"""Performance analysis tool for LLM vs app latency breakdown.

Reads JSONL logs and analyzes timing data to understand where time is spent.

Usage:
    python view_performance.py              # Analyze today's logs
    python view_performance.py --file <path>  # Analyze specific log file
    python view_performance.py --days 7     # Analyze last 7 days
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import sys
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).parent))

__all__ = ["analyze_performance_logs"]


def load_log_file(log_file: Path) -> List[Dict[str, Any]]:
    """Load JSONL log file."""
    entries = []
    if not log_file.exists():
        print(f"Log file not found: {log_file}")
        return entries
    
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    
    return entries


def extract_performance_events(entries: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Extract performance_metrics events grouped by request_id."""
    performance_by_request: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    
    for entry in entries:
        if entry.get("event_type") == "performance_metrics":
            request_id = entry.get("request_id", "unknown")
            performance_by_request[request_id].append(entry)
    
    return performance_by_request


def analyze_timing_data(timing_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze timing data and compute statistics."""
    if "__summary__" not in timing_data:
        return {}
    
    summary = timing_data["__summary__"]
    return {
        "total_seconds": summary.get("total_seconds", 0),
        "llm_seconds": summary.get("llm_seconds", 0),
        "llm_percent": summary.get("llm_percent", 0),
        "app_seconds": summary.get("app_seconds", 0),
        "app_percent": summary.get("app_percent", 0),
        "operations": {
            k: v for k, v in timing_data.items()
            if k != "__summary__"
        }
    }


def format_duration(seconds: float) -> str:
    """Format duration in seconds to readable string."""
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.0f}µs"
    elif seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    else:
        return f"{seconds:.2f}s"


def print_timing_summary(timing_data: Dict[str, Any]) -> None:
    """Print timing summary in readable format."""
    if not timing_data:
        print("  No timing data available")
        return
    
    total = timing_data.get("total_seconds", 0)
    llm_time = timing_data.get("llm_seconds", 0)
    llm_pct = timing_data.get("llm_percent", 0)
    app_time = timing_data.get("app_seconds", 0)
    app_pct = timing_data.get("app_percent", 0)
    
    print(f"  Total: {format_duration(total)}")
    print(f"  LLM:   {format_duration(llm_time)} ({llm_pct:.1f}%)")
    print(f"  App:   {format_duration(app_time)} ({app_pct:.1f}%)")
    
    operations = timing_data.get("operations", {})
    if operations:
        print("\n  Operation Breakdown:")
        # Sort by total time descending
        sorted_ops = sorted(
            operations.items(),
            key=lambda x: x[1].get("total_seconds", 0),
            reverse=True
        )
        for op_name, op_stats in sorted_ops:
            total_op = op_stats.get("total_seconds", 0)
            avg_op = op_stats.get("avg_seconds", 0)
            count = op_stats.get("count", 0)
            print(f"    {op_name:30s}: {format_duration(total_op):>10s} (avg: {format_duration(avg_op)}, count: {count})")


def analyze_performance_logs(
    log_files: List[Path],
    output_html: bool = False,
) -> Dict[str, Any]:
    """Analyze performance logs and return statistics."""
    all_entries = []
    for log_file in log_files:
        all_entries.extend(load_log_file(log_file))
    
    if not all_entries:
        print("No log entries found")
        return {}
    
    performance_events = extract_performance_events(all_entries)
    
    if not performance_events:
        print("No performance metrics found in logs")
        return {}
    
    # Analyze each request
    request_analyses = {}
    llm_times = []
    app_times = []
    total_times = []
    
    for request_id, perf_entries in performance_events.items():
        # Get the last performance entry (most complete)
        latest_entry = perf_entries[-1]
        
        # Extract timing data (remove metadata)
        timing_data = {k: v for k, v in latest_entry.items()
                      if k not in ["timestamp", "event_type", "request_id"]}
        
        analysis = analyze_timing_data(timing_data)
        request_analyses[request_id] = analysis
        
        if analysis:
            llm_times.append(analysis.get("llm_seconds", 0))
            app_times.append(analysis.get("app_seconds", 0))
            total_times.append(analysis.get("total_seconds", 0))
    
    # Compute aggregate statistics
    def percentile(data: List[float], p: float) -> float:
        """Compute percentile."""
        if not data:
            return 0
        sorted_data = sorted(data)
        idx = int(len(sorted_data) * p / 100)
        return sorted_data[min(idx, len(sorted_data) - 1)]
    
    stats = {
        "total_requests": len(request_analyses),
        "llm_total_seconds": sum(llm_times),
        "app_total_seconds": sum(app_times),
        "llm_stats": {
            "mean": sum(llm_times) / len(llm_times) if llm_times else 0,
            "min": min(llm_times) if llm_times else 0,
            "max": max(llm_times) if llm_times else 0,
            "p50": percentile(llm_times, 50),
            "p95": percentile(llm_times, 95),
            "p99": percentile(llm_times, 99),
        },
        "app_stats": {
            "mean": sum(app_times) / len(app_times) if app_times else 0,
            "min": min(app_times) if app_times else 0,
            "max": max(app_times) if app_times else 0,
            "p50": percentile(app_times, 50),
            "p95": percentile(app_times, 95),
            "p99": percentile(app_times, 99),
        },
        "total_stats": {
            "mean": sum(total_times) / len(total_times) if total_times else 0,
            "min": min(total_times) if total_times else 0,
            "max": max(total_times) if total_times else 0,
            "p50": percentile(total_times, 50),
            "p95": percentile(total_times, 95),
            "p99": percentile(total_times, 99),
        }
    }
    
    return {
        "stats": stats,
        "request_analyses": request_analyses,
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze LLM vs app latency from performance logs"
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Specific log file to analyze"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Analyze logs from last N days (default: 1)"
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path(__file__).parent / "logs",
        help="Log directory (default: web/logs/)"
    )
    
    args = parser.parse_args()
    
    # Determine which log files to analyze
    log_files = []
    if args.file:
        log_files = [args.file]
    else:
        log_dir = args.dir
        if not log_dir.exists():
            print(f"Log directory not found: {log_dir}")
            return
        
        # Get logs from last N days
        cutoff_date = datetime.now() - timedelta(days=args.days)
        for log_file in sorted(log_dir.glob("llm_interactions_*.jsonl")):
            # Parse date from filename: llm_interactions_YYYYMMDD.jsonl
            try:
                date_str = log_file.stem.split("_")[-1]
                file_date = datetime.strptime(date_str, "%Y%m%d")
                if file_date >= cutoff_date:
                    log_files.append(log_file)
            except (ValueError, IndexError):
                continue
    
    if not log_files:
        print("No log files found")
        return
    
    print(f"\nAnalyzing {len(log_files)} log file(s):\n")
    for f in log_files:
        print(f"  {f}")
    
    result = analyze_performance_logs(log_files)
    stats = result.get("stats", {})
    request_analyses = result.get("request_analyses", {})
    
    if not stats:
        return
    
    print("\n" + "="*70)
    print("PERFORMANCE SUMMARY")
    print("="*70)
    print(f"\nTotal Requests Analyzed: {stats['total_requests']}\n")
    
    print("LLM Call Latency:")
    print(f"  Mean:  {format_duration(stats['llm_stats']['mean'])}")
    print(f"  Min:   {format_duration(stats['llm_stats']['min'])}")
    print(f"  Max:   {format_duration(stats['llm_stats']['max'])}")
    print(f"  P50:   {format_duration(stats['llm_stats']['p50'])}")
    print(f"  P95:   {format_duration(stats['llm_stats']['p95'])}")
    print(f"  P99:   {format_duration(stats['llm_stats']['p99'])}")
    
    print("\nApp Processing Time:")
    print(f"  Mean:  {format_duration(stats['app_stats']['mean'])}")
    print(f"  Min:   {format_duration(stats['app_stats']['min'])}")
    print(f"  Max:   {format_duration(stats['app_stats']['max'])}")
    print(f"  P50:   {format_duration(stats['app_stats']['p50'])}")
    print(f"  P95:   {format_duration(stats['app_stats']['p95'])}")
    print(f"  P99:   {format_duration(stats['app_stats']['p99'])}")
    
    total_llm = stats['llm_total_seconds']
    total_app = stats['app_total_seconds']
    total_all = total_llm + total_app
    llm_pct = (total_llm / total_all * 100) if total_all > 0 else 0
    app_pct = (total_app / total_all * 100) if total_all > 0 else 0
    
    print("\nAggregate Time Distribution:")
    print(f"  LLM: {format_duration(total_llm)} ({llm_pct:.1f}%)")
    print(f"  App: {format_duration(total_app)} ({app_pct:.1f}%)")
    
    print("\nTotal Request Latency:")
    print(f"  Mean:  {format_duration(stats['total_stats']['mean'])}")
    print(f"  Min:   {format_duration(stats['total_stats']['min'])}")
    print(f"  Max:   {format_duration(stats['total_stats']['max'])}")
    print(f"  P50:   {format_duration(stats['total_stats']['p50'])}")
    print(f"  P95:   {format_duration(stats['total_stats']['p95'])}")
    print(f"  P99:   {format_duration(stats['total_stats']['p99'])}")
    
    # Show sample breakdowns
    if request_analyses:
        print("\n" + "="*70)
        print("SAMPLE REQUEST BREAKDOWNS (first 3)")
        print("="*70)
        for i, (request_id, analysis) in enumerate(list(request_analyses.items())[:3]):
            print(f"\nRequest {request_id}:")
            print_timing_summary(analysis)
    
    print("\n" + "="*70)


if __name__ == "__main__":
    main()
