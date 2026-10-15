"""Benchmark harness measuring pipeline throughput and latency across frames."""

import argparse
from pathlib import Path
import sys
import time
from typing import Any
import numpy as np

# Ensure project root is in sys.path when script is executed directly
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from services.counter.src.capture.source import SyntheticVideoSource
from services.counter.src.detection.detector import MockDetector
from services.counter.src.tracking.tracker import ChickenCounter, VirtualLineZone


def run_benchmark(num_frames: int = 300) -> dict[str, Any]:
    """Run pipeline benchmark and assert hardware constraints.

    Args:
        num_frames: Number of synthetic frames to process.

    Returns:
        Dict containing benchmark metrics (frames_processed, avg_fps, p95_lat, total_count).
    """
    source = SyntheticVideoSource(width=640, height=480, fps=30)
    detector = MockDetector(min_confidence=0.8)
    line_zone = VirtualLineZone(start=(0, 240), end=(640, 240), direction="down")
    counter = ChickenCounter(line_zone=line_zone, line_id="lineA")

    source.start()
    latencies: list[float] = []

    print(f"Starting benchmark across {num_frames} frames...")
    start_time = time.perf_counter()

    for _ in range(num_frames):
        f_start = time.perf_counter()
        ret, frame = source.read()
        if not ret or frame is None:
            break

        detections = detector.predict(frame)
        counter.update(detections, timestamp=time.time())
        latencies.append((time.perf_counter() - f_start) * 1000.0)

    total_time = time.perf_counter() - start_time
    source.stop()

    avg_fps = len(latencies) / total_time if total_time > 0 else 0.0
    p95_lat = float(np.percentile(latencies, 95)) if latencies else 0.0

    print("--- Benchmark Results ---")
    print(f"Total Frames Processed: {len(latencies)}")
    print(f"Average FPS: {avg_fps:.2f} frames/sec")
    print(f"p95 Latency: {p95_lat:.2f} ms")
    print(f"Total Chickens Counted: {counter.total_count}")
    assert p95_lat < 50.0, f"Latency violation: {p95_lat} ms >= 50 ms target"
    assert avg_fps >= 30.0, f"FPS violation: {avg_fps} < 30 fps target"
    print("ALL HARDWARE CONSTRAINTS SATISFIED!")

    return {
        "frames_processed": len(latencies),
        "total_time_sec": total_time,
        "avg_fps": float(avg_fps),
        "p95_lat": float(p95_lat),
        "p95_lat_ms": float(p95_lat),
        "total_count": counter.total_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline Benchmark Harness")
    parser.add_argument(
        "--frames",
        type=int,
        default=300,
        help="Number of frames to benchmark (default: 300)",
    )
    args = parser.parse_args()
    run_benchmark(num_frames=args.frames)


if __name__ == "__main__":
    main()
