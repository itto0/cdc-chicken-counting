"""Production entrypoint runner for the edge counter service."""

import logging
import os
from pathlib import Path
import signal
import sys
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

logger = logging.getLogger("counter.service")


class CounterService:
    """Manages the edge counting pipeline lifecycle and sync dispatcher."""

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
    ) -> None:
        self.line_id = line_id
        self.video_source_type = video_source_type.lower()
        self.video_path = video_path
        self.api_sync_url = api_sync_url
        self.db_path = db_path
        self.sync_interval_sec = sync_interval_sec
        self.target_fps = target_fps

        self.running = False
        self.total_frames_processed = 0

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

    def stop(self) -> None:
        """Signal the pipeline loop to stop."""
        self.running = False

    def run(self, max_frames: Optional[int] = None) -> int:
        """Run the counting pipeline loop: Capture -> Detect -> Track/Count -> Outbox -> Sync.

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
        self.source.start()
        last_sync_time = time.perf_counter()

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

                # 1. Detect
                detections = self.detector.predict(frame)

                # 2. Track & Count
                events = self.counter.update(detections, timestamp=frame_start)

                # 3. LocalStorage Outbox
                for ev in events:
                    self.storage.insert_event(self.line_id, ev)
                    logger.debug("Saved count event: track_id=%d, line=%s", ev.track_id, self.line_id)

                # 4. Periodic Sync Dispatcher
                now = time.perf_counter()
                if now - last_sync_time >= self.sync_interval_sec:
                    synced = self.dispatcher.sync_once()
                    if synced > 0:
                        logger.info("Synced %d outbox records to central API", synced)
                    last_sync_time = now

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
        """Release video source and flush unsynced records."""
        logger.info("Cleaning up counter pipeline resources...")
        try:
            self.source.stop()
        except Exception as e:
            logger.warning("Error stopping video source: %s", e)

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
