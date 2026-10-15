"""Production entrypoint runner for the edge counter service."""

from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import signal
import sys
import threading
import time
from typing import Optional

# Ensure project root is in sys.path when script is executed directly
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from services.counter.src.capture.source import (
    FileVideoSource,
    SyntheticVideoSource,
    VideoSource,
)
from services.counter.src.detection.detector import Detector, MockDetector
from services.counter.src.storage.db import LocalStorage
from services.counter.src.sync.dispatcher import OutboxSyncDispatcher
from services.counter.src.tracking.tracker import ChickenCounter, VirtualLineZone
from shared.contracts import CountAggregateDTO, HealthSampleDTO

logger = logging.getLogger("counter.service")


class CounterService:
    """Manages the edge counting pipeline lifecycle, telemetry, and background sync dispatcher."""

    def __init__(
        self,
        line_id: str = "lineA",
        video_source_type: str = "synthetic",
        video_path: str = "",
        api_sync_url: str = "http://localhost:8000/api/v1/sync/batch",
        db_path: str = "counter_outbox.db",
        sync_interval_sec: float = 5.0,
        source: Optional[VideoSource] = None,
        detector: Optional[Detector] = None,
        counter: Optional[ChickenCounter] = None,
        storage: Optional[LocalStorage] = None,
        dispatcher: Optional[OutboxSyncDispatcher] = None,
        target_fps: float = 0.0,
        aggregate_window_sec: float = 60.0,
        health_interval_sec: float = 10.0,
    ) -> None:
        self.line_id = line_id
        self.video_source_type = video_source_type.lower()
        self.video_path = video_path
        self.api_sync_url = api_sync_url
        self.db_path = db_path
        self.sync_interval_sec = sync_interval_sec
        self.target_fps = target_fps
        self.aggregate_window_sec = aggregate_window_sec
        self.health_interval_sec = health_interval_sec

        self.running = False
        self.total_frames_processed = 0

        # Background sync worker control
        self._stop_event = threading.Event()
        self._sync_thread: Optional[threading.Thread] = None

        # Aggregation state tracking
        self._window_start_utc = datetime.now(timezone.utc)
        self._window_last_calc_time = time.perf_counter()
        self._window_count = 0
        self._window_confidences: list[float] = []

        # Health metrics tracking
        self._health_last_calc_time = time.perf_counter()
        self._health_frame_count = 0
        self._health_latencies_ms: list[float] = []

        # Storage
        self.storage = storage or LocalStorage(db_path=self.db_path)
        self.storage.init_db()

        # Dispatcher
        self.dispatcher = dispatcher or OutboxSyncDispatcher(
            storage=self.storage,
            api_url=self.api_sync_url,
            line_id=self.line_id,
        )

        # Video source
        if source is not None:
            self.source = source
        elif self.video_source_type in ("file", "rtsp"):
            self.source = FileVideoSource(file_path=self.video_path, loop=True)
        else:
            self.source = SyntheticVideoSource(width=640, height=480, fps=30)

        # Detector
        self.detector = detector or MockDetector(min_confidence=0.8)

        # Tracker / Counter
        if counter is not None:
            self.counter = counter
        else:
            line_zone = VirtualLineZone(
                start=(0.0, 240.0),
                end=(640.0, 240.0),
                direction="down",
            )
            self.counter = ChickenCounter(line_zone=line_zone, line_id=self.line_id)

    def _sync_worker(self) -> None:
        """Background worker periodically pushing unsynced outbox batches to central API."""
        logger.info("Background sync worker started for line '%s'", self.line_id)
        while not self._stop_event.is_set():
            try:
                synced = self.dispatcher.sync_once()
                if synced > 0:
                    logger.debug("Background synced %d outbox records to central API", synced)
            except Exception as e:
                logger.warning("Error in background sync worker: %s", e)

            # Determine sleep duration based on backoff or configured interval
            sleep_time = self.sync_interval_sec
            backoff = getattr(self.dispatcher, "backoff_sec", 1.0)
            if backoff > 1.0:
                sleep_time = max(sleep_time, backoff)

            self._stop_event.wait(timeout=sleep_time)

        logger.info("Background sync worker stopped for line '%s'", self.line_id)

    def _record_aggregate(self, now_perf: Optional[float] = None) -> None:
        """Calculate and store a window count aggregate in LocalStorage."""
        if now_perf is None:
            now_perf = time.perf_counter()

        window_end_utc = datetime.now(timezone.utc)
        elapsed_sec = max(0.001, (window_end_utc - self._window_start_utc).total_seconds())
        rate_per_min = self._window_count * (60.0 / elapsed_sec)

        if rate_per_min >= 130.0:
            status = "NORMAL"
        elif rate_per_min >= 110.0:
            status = "WARNING"
        else:
            status = "CRITICAL"

        conf_avg = (
            sum(self._window_confidences) / len(self._window_confidences)
            if self._window_confidences
            else 1.0
        )

        agg = CountAggregateDTO(
            window_start=self._window_start_utc,
            window_end=window_end_utc,
            count=self._window_count,
            rate_per_min=round(rate_per_min, 2),
            confidence_avg=round(min(1.0, max(0.0, conf_avg)), 3),
            status=status,
        )
        try:
            self.storage.insert_aggregate(self.line_id, agg)
            logger.debug(
                "Recorded aggregate: %d birds, rate=%.1f/min, status=%s",
                self._window_count,
                rate_per_min,
                status,
            )
        except Exception as e:
            logger.warning("Failed to record aggregate: %s", e)

        # Reset window tracking
        self._window_start_utc = window_end_utc
        self._window_last_calc_time = now_perf
        self._window_count = 0
        self._window_confidences = []

    def _record_health(
        self, now_perf: Optional[float] = None, stream_state: str = "ONLINE"
    ) -> None:
        """Calculate and store health sample in LocalStorage."""
        if now_perf is None:
            now_perf = time.perf_counter()

        elapsed_sec = max(0.001, now_perf - self._health_last_calc_time)
        fps = self._health_frame_count / elapsed_sec

        if self._health_latencies_ms:
            sorted_lat = sorted(self._health_latencies_ms)
            p95_idx = int(0.95 * len(sorted_lat))
            latency_p95 = sorted_lat[min(p95_idx, len(sorted_lat) - 1)]
        else:
            latency_p95 = 0.0

        cpu_pct = 0.0
        mem_pct = 0.0
        try:
            import psutil
            cpu_pct = float(psutil.cpu_percent(interval=None))
            mem_pct = float(psutil.virtual_memory().percent)
        except Exception:
            pass

        if stream_state == "ONLINE" and fps < 5.0 and self.total_frames_processed > 0:
            stream_state = "DEGRADED"

        health = HealthSampleDTO(
            fps=round(fps, 1),
            latency_p95_ms=round(latency_p95, 2),
            cpu_pct=round(min(100.0, max(0.0, cpu_pct)), 1),
            mem_pct=round(min(100.0, max(0.0, mem_pct)), 1),
            stream_state=stream_state,
            model_name=getattr(self.detector, "model_name", "yolo26n")
            if hasattr(self.detector, "model_name")
            else "yolo26n",
            model_version="v1.0",
        )
        try:
            self.storage.insert_health(self.line_id, health)
            logger.debug(
                "Recorded health: fps=%.1f, latency=%.1fms, state=%s",
                fps,
                latency_p95,
                stream_state,
            )
        except Exception as e:
            logger.warning("Failed to record health: %s", e)

        # Reset health tracking
        self._health_last_calc_time = now_perf
        self._health_frame_count = 0
        self._health_latencies_ms = []

    def stop(self) -> None:
        """Signal the pipeline loop and background sync worker to stop."""
        self.running = False
        self._stop_event.set()

    def run(self, max_frames: Optional[int] = None) -> int:
        """Run the counting pipeline loop: Capture -> Detect -> Track/Count -> LocalStorage.

        Syncing is handled decoupled in a background thread to prevent frame dropping.

        Args:
            max_frames: Optional limit on frames to process (useful for tests/benchmarks).

        Returns:
            Total chickens counted during this run.
        """
        logger.info(
            "Starting counter service for line '%s' (source=%s, sync_url=%s, interval=%.1fs)",
            self.line_id,
            self.video_source_type,
            self.api_sync_url,
            self.sync_interval_sec,
        )
        self.running = True
        self._stop_event.clear()

        # Start background sync dispatcher thread
        self._sync_thread = threading.Thread(
            target=self._sync_worker,
            daemon=True,
            name=f"SyncWorker-{self.line_id}",
        )
        self._sync_thread.start()

        self.source.start()

        now_utc = datetime.now(timezone.utc)
        now_perf = time.perf_counter()
        self._window_start_utc = now_utc
        self._window_last_calc_time = now_perf
        self._window_count = 0
        self._window_confidences = []

        self._health_last_calc_time = now_perf
        self._health_frame_count = 0
        self._health_latencies_ms = []

        try:
            while self.running:
                if max_frames is not None and self.total_frames_processed >= max_frames:
                    logger.info("Reached target frame limit of %d frames", max_frames)
                    break

                frame_start = time.perf_counter()
                ret, frame = self.source.read()
                if not ret or frame is None:
                    logger.info("End of stream or unable to read frame.")
                    break

                self.total_frames_processed += 1
                self._health_frame_count += 1

                # 1. Detect
                t0 = time.perf_counter()
                detections = self.detector.predict(frame)

                # 2. Track & Count
                events = self.counter.update(detections, timestamp=time.time())
                latency_ms = (time.perf_counter() - t0) * 1000.0
                self._health_latencies_ms.append(latency_ms)

                # 3. LocalStorage Outbox (non-blocking)
                for ev in events:
                    self.storage.insert_event(self.line_id, ev)
                    self._window_count += 1
                    self._window_confidences.append(ev.confidence)
                    logger.debug(
                        "Saved count event: track_id=%d, line=%s",
                        ev.track_id,
                        self.line_id,
                    )

                # 4. Periodic Aggregates calculation
                now = time.perf_counter()
                if now - self._window_last_calc_time >= self.aggregate_window_sec:
                    self._record_aggregate(now)

                # 5. Periodic Health Telemetry recording
                if now - self._health_last_calc_time >= self.health_interval_sec:
                    self._record_health(now)

                # Optional frame rate pacing
                if self.target_fps > 0:
                    elapsed = time.perf_counter() - frame_start
                    delay = (1.0 / self.target_fps) - elapsed
                    if delay > 0:
                        time.sleep(delay)

        finally:
            self._cleanup()

        return self.counter.total_count

    def _cleanup(self) -> None:
        """Stop background worker, release video source, record telemetry, and flush unsynced records."""
        logger.info("Cleaning up counter pipeline resources...")
        self.running = False
        self._stop_event.set()

        try:
            self.source.stop()
        except Exception as e:
            logger.warning("Error stopping video source: %s", e)

        # Record final telemetry if pending
        if self._window_count > 0 or self._health_frame_count > 0:
            try:
                if self._window_count > 0:
                    self._record_aggregate()
                if self._health_frame_count > 0:
                    self._record_health()
            except Exception as e:
                logger.warning("Error recording final telemetry: %s", e)

        # Wait for background sync thread to finish current iteration
        if self._sync_thread is not None and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=2.0)

        # Flush any remaining items in outbox before exit
        try:
            synced = self.dispatcher.sync_once()
            if synced > 0:
                logger.info("Flushed %d remaining records to central API", synced)
        except Exception as e:
            logger.warning("Error during final outbox sync: %s", e)

        try:
            self.dispatcher.close()
        except Exception as e:
            logger.warning("Error closing dispatcher: %s", e)

        logger.info(
            "Counter service stopped. Frames: %d, Total counted: %d",
            self.total_frames_processed,
            self.counter.total_count,
        )


def main() -> None:
    """Entrypoint reading configuration from environment variables and running service."""
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    line_id = os.getenv("LINE_ID", "lineA")
    video_source_type = os.getenv("VIDEO_SOURCE_TYPE", "synthetic")
    video_path = os.getenv("VIDEO_PATH", "")
    api_sync_url = os.getenv("API_SYNC_URL", "http://localhost:8000/api/v1/sync/batch")
    db_path = os.getenv("DB_PATH", "counter_outbox.db")
    sync_interval_sec = float(os.getenv("SYNC_INTERVAL_SEC", "5.0"))
    aggregate_window_sec = float(os.getenv("AGGREGATE_WINDOW_SEC", "60.0"))
    health_interval_sec = float(os.getenv("HEALTH_INTERVAL_SEC", "10.0"))
    max_frames_str = os.getenv("MAX_FRAMES", "")
    max_frames = int(max_frames_str) if max_frames_str.strip().isdigit() else None
    target_fps_str = os.getenv("TARGET_FPS", "0.0")
    try:
        target_fps = float(target_fps_str)
    except ValueError:
        target_fps = 0.0

    service = CounterService(
        line_id=line_id,
        video_source_type=video_source_type,
        video_path=video_path,
        api_sync_url=api_sync_url,
        db_path=db_path,
        sync_interval_sec=sync_interval_sec,
        target_fps=target_fps,
        aggregate_window_sec=aggregate_window_sec,
        health_interval_sec=health_interval_sec,
    )

    def handle_shutdown(signum: int, frame: object) -> None:
        logger.info("Received termination signal (%d), stopping...", signum)
        service.stop()

    try:
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)
    except (ValueError, AttributeError):
        pass

    service.run(max_frames=max_frames)


if __name__ == "__main__":
    main()
