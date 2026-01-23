"""Performance timing tracker for LLM and app operations.

Provides structured timing measurements for the recommendation flow to understand
how much time is spent in LLM API calls vs app processing.

Example:
    from timing import timer, get_timings
    
    with timer("llm_call"):
        response = llm_api.call()
    
    # Log all timings
    timings = get_timings()
    log_interaction("performance", timings)
"""

import time
from contextlib import contextmanager
from typing import Dict, Any, Optional

try:
    from flask import g, has_request_context
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    g = None
    has_request_context = None

__all__ = ["timer", "get_timings", "reset_timings", "TimingTracker"]


class TimingTracker:
    """Track timing for multiple operations within a request."""
    
    def __init__(self):
        """Initialize tracker."""
        self.timings: Dict[str, Dict[str, Any]] = {}
        self.active_timers: Dict[str, float] = {}
    
    def start(self, operation: str) -> None:
        """Start timing an operation."""
        self.active_timers[operation] = time.time()
    
    def end(self, operation: str) -> float:
        """End timing and return duration in seconds."""
        if operation not in self.active_timers:
            return 0.0
        
        duration = time.time() - self.active_timers.pop(operation)
        
        if operation not in self.timings:
            self.timings[operation] = {
                "count": 0,
                "total_seconds": 0.0,
                "min_seconds": float('inf'),
                "max_seconds": 0.0,
            }
        
        stats = self.timings[operation]
        stats["count"] += 1
        stats["total_seconds"] += duration
        stats["min_seconds"] = min(stats["min_seconds"], duration)
        stats["max_seconds"] = max(stats["max_seconds"], duration)
        
        return duration
    
    @contextmanager
    def measure(self, operation: str):
        """Context manager for timing an operation."""
        self.start(operation)
        try:
            yield
        finally:
            self.end(operation)
    
    def get_all(self) -> Dict[str, Any]:
        """Get all timings, cleaned up for JSON serialization."""
        result = {}
        for op, stats in self.timings.items():
            result[op] = {
                "count": stats["count"],
                "total_seconds": round(stats["total_seconds"], 3),
                "avg_seconds": round(stats["total_seconds"] / stats["count"], 3) if stats["count"] > 0 else 0,
                "min_seconds": round(stats["min_seconds"], 3) if stats["min_seconds"] != float('inf') else 0,
                "max_seconds": round(stats["max_seconds"], 3),
            }
        
        # Add summary breakdown
        if result:
            llm_time = sum(
                stats["total_seconds"] 
                for op, stats in self.timings.items() 
                if "llm" in op.lower()
            )
            app_time = sum(
                stats["total_seconds"] 
                for op, stats in self.timings.items() 
                if "llm" not in op.lower()
            )
            total_time = llm_time + app_time
            
            result["__summary__"] = {
                "total_seconds": round(total_time, 3),
                "llm_seconds": round(llm_time, 3),
                "llm_percent": round((llm_time / total_time * 100) if total_time > 0 else 0, 1),
                "app_seconds": round(app_time, 3),
                "app_percent": round((app_time / total_time * 100) if total_time > 0 else 0, 1),
            }
        
        return result
    
    def reset(self) -> None:
        """Reset all timings."""
        self.timings.clear()
        self.active_timers.clear()


# Global tracker instance for non-Flask contexts (e.g., CLI tools, tests)
_tracker: Optional[TimingTracker] = None


def _get_tracker() -> TimingTracker:
    """Get or create the tracker for the current context.
    
    In Flask request context, uses flask.g for thread-safe per-request storage.
    Otherwise, uses a global tracker for CLI tools and tests.
    """
    if FLASK_AVAILABLE and has_request_context():
        # Use Flask's request-scoped storage for thread safety
        if not hasattr(g, 'timing_tracker'):
            g.timing_tracker = TimingTracker()
        return g.timing_tracker
    else:
        # Fall back to global tracker for CLI tools and tests
        global _tracker
        if _tracker is None:
            _tracker = TimingTracker()
        return _tracker


@contextmanager
def timer(operation: str):
    """Context manager for timing an operation.
    
    Args:
        operation: Name of the operation (e.g., "job_identification", "llm_call_recommendation")
    
    Example:
        with timer("llm_call"):
            response = openai_client.chat.completions.create(...)
        
        with timer("candidate_selection"):
            products = select_candidates(categories, fit_values)
    """
    tracker = _get_tracker()
    with tracker.measure(operation):
        yield


def get_timings() -> Dict[str, Any]:
    """Get all recorded timings with summary statistics.
    
    Returns:
        Dict with operation timings and __summary__ key containing:
        - total_seconds: Total elapsed time
        - llm_seconds: Time spent in LLM calls
        - llm_percent: Percentage of time in LLM
        - app_seconds: Time spent in app processing
        - app_percent: Percentage of time in app
    
    Example:
        timings = get_timings()
        print(f"LLM: {timings['__summary__']['llm_percent']}%")
        print(f"App: {timings['__summary__']['app_percent']}%")
    """
    return _get_tracker().get_all()


def reset_timings() -> None:
    """Reset all timings for a new request.
    
    In Flask request context, this clears the request-scoped tracker.
    Otherwise, it resets the global tracker for CLI tools and tests.
    """
    if FLASK_AVAILABLE and has_request_context():
        # Clear Flask's request-scoped storage
        if hasattr(g, 'timing_tracker'):
            g.timing_tracker.reset()
        else:
            g.timing_tracker = TimingTracker()
    else:
        # Reset global tracker for CLI tools and tests
        tracker = _get_tracker()
        tracker.reset()
