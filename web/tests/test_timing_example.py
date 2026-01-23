"""Example test demonstrating the timing system.

Run with: python web/tests/test_timing_example.py
"""

import time
from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from timing import timer, get_timings, reset_timings
else:
    from ..timing import timer, get_timings, reset_timings


def test_timing_basic():
    """Test basic timing functionality."""
    reset_timings()
    
    # Simulate a fast operation
    with timer("fast_operation"):
        time.sleep(0.05)
    
    # Simulate a slow operation
    with timer("slow_operation"):
        time.sleep(0.15)
    
    timings = get_timings()
    
    # Verify operations were tracked
    assert "fast_operation" in timings
    assert "slow_operation" in timings
    assert "__summary__" in timings
    
    # Verify timing values
    fast_time = timings["fast_operation"]["total_seconds"]
    slow_time = timings["slow_operation"]["total_seconds"]
    
    assert 0.04 < fast_time < 0.08  # Allow some variance
    assert 0.14 < slow_time < 0.18
    
    print(f"✓ Fast operation: {fast_time:.3f}s")
    print(f"✓ Slow operation: {slow_time:.3f}s")
    print(f"✓ Summary: {timings['__summary__']}")


def test_timing_llm_vs_app():
    """Simulate LLM vs app latency breakdown."""
    reset_timings()
    
    # Simulate LLM call
    with timer("llm_call_job_identification"):
        time.sleep(0.5)
    
    # Simulate app processing
    with timer("app_validate_categories"):
        time.sleep(0.05)
    
    with timer("app_candidate_selection"):
        time.sleep(0.08)
    
    # Simulate another LLM call
    with timer("llm_call_recommendation"):
        time.sleep(0.8)
    
    timings = get_timings()
    summary = timings["__summary__"]
    
    # Verify percentages
    assert 70 < summary["llm_percent"] < 95  # ~80% LLM time
    assert 5 < summary["app_percent"] < 30   # ~20% app time
    
    print(f"\nLLM vs App Breakdown:")
    print(f"  Total: {summary['total_seconds']:.3f}s")
    print(f"  LLM: {summary['llm_seconds']:.3f}s ({summary['llm_percent']:.1f}%)")
    print(f"  App: {summary['app_seconds']:.3f}s ({summary['app_percent']:.1f}%)")


def test_timing_repeated_operations():
    """Test aggregation of repeated operations."""
    reset_timings()
    
    # Simulate multiple iterations
    for i in range(3):
        with timer("loop_operation"):
            time.sleep(0.05)
    
    timings = get_timings()
    op = timings["loop_operation"]
    
    assert op["count"] == 3
    assert 0.14 < op["total_seconds"] < 0.18  # 3 × 0.05s
    assert 0.04 < op["avg_seconds"] < 0.07
    
    print(f"\nRepeated Operations:")
    print(f"  Operation: loop_operation")
    print(f"  Count: {op['count']}")
    print(f"  Total: {op['total_seconds']:.3f}s")
    print(f"  Average: {op['avg_seconds']:.3f}s")
    print(f"  Min: {op['min_seconds']:.3f}s")
    print(f"  Max: {op['max_seconds']:.3f}s")


if __name__ == "__main__":
    print("Running timing system examples...\n")
    
    try:
        test_timing_basic()
        test_timing_llm_vs_app()
        test_timing_repeated_operations()
        print("\n✅ All examples passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
