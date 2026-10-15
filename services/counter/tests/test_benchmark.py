"""Tests for benchmark harness."""

from unittest.mock import patch
import pytest
from services.counter.benchmark import main, run_benchmark


def test_run_benchmark_metrics():
    """Verify run_benchmark processes frames and meets performance criteria."""
    metrics = run_benchmark(num_frames=60)

    assert metrics["frames_processed"] == 60
    assert metrics["avg_fps"] >= 30.0
    assert metrics["p95_lat_ms"] < 50.0
    assert metrics["total_count"] >= 0
    assert metrics["total_time_sec"] > 0


def test_benchmark_cli_main():
    """Verify benchmark CLI parses args and runs benchmark."""
    with patch("sys.argv", ["benchmark.py", "--frames", "20"]):
        # Should not raise exception
        main()
