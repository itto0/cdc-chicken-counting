"""Production entrypoint runner for the edge counter service."""

import argparse
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import signal
import sys
import threading
import time
from typing import Optional, Sequence

# Ensure counter root and monorepo root are in sys.path when script is executed directly
# Add counter root to sys.path, and add monorepo root only if running inside monorepo
counter_root = Path(__file__).resolve().parent
monorepo_root = counter_root.parent.parent

if str(counter_root) not in sys.path:
    sys.path.insert(0, str(counter_root))

if (monorepo_root / "services").is_dir() and str(monorepo_root) not in sys.path:
    sys.path.append(str(monorepo_root))

try:
    from src.env import init_env
except ImportError:
    try:
        from services.counter.src.env import init_env
    except ImportError:
        from shared.env import init_env

init_env()

try:
    from src.capture.source import (
        FileVideoSource,
        SyntheticVideoSource,
        VideoSource,
    )
    from src.detection.detector import (
        Detector,
        MockDetector,
        ONNXDetector,
        ShackleDetector,
    )
    from src.storage.db import LocalStorage
    from src.sync.dispatcher import OutboxSyncDispatcher
    from src.tracking.tracker import ChickenCounter, VirtualLineZone
except ImportError:
    from services.counter.src.capture.source import (
        FileVideoSource,
        SyntheticVideoSource,
        VideoSource,
    )
    from services.counter.src.detection.detector import (
        Detector,
        MockDetector,
        ONNXDetector,
        ShackleDetector,
    )
    from services.counter.src.storage.db import LocalStorage
    from services.counter.src.sync.dispatcher import OutboxSyncDispatcher
    from services.counter.src.tracking.tracker import ChickenCounter, VirtualLineZone

try:
    from src.contracts import CountAggregateDTO, HealthSampleDTO
except ImportError:
    try:
        from services.counter.src.contracts import CountAggregateDTO, HealthSampleDTO
    except ImportError:
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
        loop: bool = False,
        line_coords: Optional[tuple[float, float, float, float]] = None,
        line_direction: str = "down",
        enable_sync: bool = True,
        cli_display: bool = True,
        show_window: bool = False,
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
        self.loop = loop
        self.line_coords = line_coords
        self.line_direction = line_direction
        self.enable_sync = enable_sync
        self.cli_display = cli_display
        self.show_window = show_window

        self.running = False
        self.total_frames_processed = 0
        self._start_time_perf: Optional[float] = None
        self._custom_line_set = line_coords is not None

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
        self._all_latencies_ms: list[float] = []

        # Storage
        self.storage = storage or LocalStorage(db_path=self.db_path)
        self.storage.init_db()

        # Dispatcher (only initialized if enable_sync is True or explicitly provided)
        if dispatcher is not None:
            self.dispatcher: Optional[OutboxSyncDispatcher] = dispatcher
        elif self.enable_sync:
            self.dispatcher = OutboxSyncDispatcher(
                storage=self.storage,
                api_url=self.api_sync_url,
                line_id=self.line_id,
            )
        else:
            self.dispatcher = None

        # Video source
        if source is not None:
            self.source = source
        elif self.video_source_type in ("file", "rtsp"):
            self.source = FileVideoSource(file_path=self.video_path, loop=self.loop)
        else:
            self.source = SyntheticVideoSource(width=640, height=480, fps=30)

        # Detector
        self.detector = detector or MockDetector(min_confidence=0.8)

        # Tracker / Counter
        if counter is not None:
            self.counter = counter
        else:
            if self.line_coords is not None:
                start_pt = (self.line_coords[0], self.line_coords[1])
                end_pt = (self.line_coords[2], self.line_coords[3])
            elif self.line_direction in ("right", "left"):
                start_pt = (320.0, 50.0)
                end_pt = (320.0, 430.0)
            else:
                start_pt = (0.0, 240.0)
                end_pt = (640.0, 240.0)
            line_zone = VirtualLineZone(
                start=start_pt,
                end=end_pt,
                direction=self.line_direction,
            )
            self.counter = ChickenCounter(line_zone=line_zone, line_id=self.line_id)

    def _sync_worker(self) -> None:
        """Background worker periodically pushing unsynced outbox batches to central API."""
        if self.dispatcher is None:
            return
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
        self.running = True
        self._stop_event.clear()
        self.total_frames_processed = 0
        self._start_time_perf = time.perf_counter()

        # Start background sync dispatcher thread if enabled
        if self.enable_sync and self.dispatcher is not None:
            if self._sync_thread is None or not self._sync_thread.is_alive():
                self._sync_thread = threading.Thread(
                    target=self._sync_worker,
                    daemon=True,
                    name=f"SyncWorker-{self.line_id}",
                )
                self._sync_thread.start()

        self.source.start()

        # If source is a file and dimensions are known, auto-adjust virtual line before printing header
        if not self._custom_line_set and hasattr(self.source, "cap") and self.source.cap is not None:
            try:
                import cv2
                vw = int(self.source.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                vh = int(self.source.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if vw > 0 and vh > 0 and (vw, vh) != (640, 480):
                    if self.counter.line_zone.direction in ("right", "left"):
                        mid_x = float(vw // 2)
                        self.counter.line_zone.start = (mid_x, float(vh) * 0.20)
                        self.counter.line_zone.end = (mid_x, float(vh) * 0.90)
                    else:
                        mid_y = float(vh // 2)
                        self.counter.line_zone.start = (0.0, mid_y)
                        self.counter.line_zone.end = (float(vw), mid_y)
                    self.counter.max_distance = min(60.0, max(35.0, float(vw) * 0.03))
            except Exception:
                pass

        if self.cli_display:
            self._print_cli_header()

        now_utc = datetime.now(timezone.utc)
        now_perf = time.perf_counter()
        self._window_start_utc = now_utc
        self._window_last_calc_time = now_perf
        self._window_count = 0
        self._window_confidences = []

        self._health_last_calc_time = now_perf
        self._health_frame_count = 0
        self._health_latencies_ms = []
        self._all_latencies_ms = []

        last_progress_print = 0.0

        try:
            while self.running:
                if max_frames is not None and self.total_frames_processed >= max_frames:
                    if self.cli_display:
                        print(f"\nReached max frames limit ({max_frames}).")
                    break

                frame_start = time.perf_counter()
                ret, frame = self.source.read()
                if not ret or frame is None:
                    if self.cli_display:
                        print("\nReached end of video stream.")
                    break

                self.total_frames_processed += 1
                self._health_frame_count += 1

                # On first frame, auto-adjust virtual line to frame dimensions if not custom-set
                if not self._custom_line_set and self.total_frames_processed == 1:
                    h, w = frame.shape[:2]
                    if (w, h) != (640, 480):
                        if self.counter.line_zone.direction in ("right", "left"):
                            mid_x = float(w // 2)
                            self.counter.line_zone.start = (mid_x, float(h) * 0.20)
                            self.counter.line_zone.end = (mid_x, float(h) * 0.90)
                        else:
                            mid_y = float(h // 2)
                            self.counter.line_zone.start = (0.0, mid_y)
                            self.counter.line_zone.end = (float(w), mid_y)
                        self.counter.max_distance = min(60.0, max(35.0, float(w) * 0.03))

                # 1. Detect
                t0 = time.perf_counter()
                detections = self.detector.predict(frame)

                # 2. Track & Count
                events = self.counter.update(detections, timestamp=time.time())
                latency_ms = (time.perf_counter() - t0) * 1000.0
                self._health_latencies_ms.append(latency_ms)
                self._all_latencies_ms.append(latency_ms)

                # 3. LocalStorage Outbox (non-blocking)
                for ev in events:
                    self.storage.insert_event(self.line_id, ev)
                    self._window_count += 1
                    self._window_confidences.append(ev.confidence)
                    if self.cli_display:
                        # Clear in-place line and print count event
                        sys.stdout.write("\r" + " " * 80 + "\r")
                        print(
                            f" [COUNT +1] Frame #{self.total_frames_processed:<5d} | "
                            f"Track #{ev.track_id:<3d} | "
                            f"Conf: {ev.confidence:>5.1%} | "
                            f"Line Total: {self.counter.total_count}"
                        )
                    logger.debug(
                        "Saved count event: track_id=%d, line=%s",
                        ev.track_id,
                        self.line_id,
                    )

                # Optional visual preview window
                if self.show_window:
                    self._render_window_frame(frame, detections, events)
                    try:
                        import cv2
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            if self.cli_display:
                                print("\nUser pressed 'q' in preview window. Stopping.")
                            break
                    except Exception:
                        pass

                # 4. Periodic Aggregates calculation
                now = time.perf_counter()
                if now - self._window_last_calc_time >= self.aggregate_window_sec:
                    self._record_aggregate(now)

                # 5. Periodic Health Telemetry recording
                if now - self._health_last_calc_time >= self.health_interval_sec:
                    self._record_health(now)

                # 6. Live CLI status line update
                if self.cli_display and (now - last_progress_print >= 0.15 or self.total_frames_processed == 1):
                    last_progress_print = now
                    elapsed_total = max(0.001, now - (self._start_time_perf or now))
                    curr_fps = self.total_frames_processed / elapsed_total
                    curr_rate = self.counter.total_count * (60.0 / elapsed_total)
                    recent_lat = self._all_latencies_ms[-1] if self._all_latencies_ms else 0.0
                    sys.stdout.write(
                        f"\r[Frame {self.total_frames_processed:5d}] "
                        f"Chickens: {self.counter.total_count:4d} | "
                        f"Rate: {curr_rate:5.1f}/min | "
                        f"Speed: {curr_fps:5.1f} fps | "
                        f"Latency: {recent_lat:4.1f}ms   "
                    )
                    sys.stdout.flush()

                # Optional frame rate pacing
                if self.target_fps > 0:
                    elapsed = time.perf_counter() - frame_start
                    delay = (1.0 / self.target_fps) - elapsed
                    if delay > 0:
                        time.sleep(delay)

        finally:
            self._cleanup()
            if self.cli_display:
                self._print_cli_summary()

        return self.counter.total_count

    def _render_window_frame(
        self, frame: object, detections: list, events: list
    ) -> Optional[object]:
        """Render annotations on frame and show in an OpenCV window."""
        try:
            import cv2
            import numpy as np

            if not isinstance(frame, np.ndarray):
                return None
            vis = frame.copy()
            h, w = vis.shape[:2]

            # Draw virtual line
            p1 = (int(self.counter.line_zone.start[0]), int(self.counter.line_zone.start[1]))
            p2 = (int(self.counter.line_zone.end[0]), int(self.counter.line_zone.end[1]))
            line_color = (0, 0, 255) if events else (0, 255, 0)
            cv2.line(vis, p1, p2, line_color, 3)
            cv2.putText(
                vis,
                f"COUNT LINE ({self.counter.line_zone.direction})",
                (p1[0] + 10, max(30, p1[1] - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                line_color,
                2,
            )

            # Track rendered detection coordinates to avoid duplicate bounding boxes
            rendered_boxes: set[tuple[int, int, int, int]] = set()

            # Draw active tracks with their track ID, dynamic color, and status label
            for track_id, track in self.counter.tracks.items():
                if track.missed_frames > 0:
                    continue  # Do not render stale tracks / ghosts

                x1, y1, x2, y2 = (
                    int(track.bbox[0]),
                    int(track.bbox[1]),
                    int(track.bbox[2]),
                    int(track.bbox[3]),
                )
                rendered_boxes.add((x1, y1, x2, y2))

                if track.counted:
                    box_color = (0, 220, 0)  # Green
                    label = f"{track.class_name} #{track_id} {track.confidence:.2f} [COUNTED]"
                else:
                    box_color = (0, 180, 255)  # Orange
                    label = f"{track.class_name} #{track_id} {track.confidence:.2f}"

                cv2.rectangle(vis, (x1, y1), (x2, y2), box_color, 2)
                cv2.putText(
                    vis,
                    label,
                    (x1, max(20, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    box_color,
                    1,
                )

                # Track anchor center
                cx, cy = int(track.current_anchor[0]), int(track.current_anchor[1])
                cv2.circle(vis, (cx, cy), 5, (0, 255, 255), -1)

            # Draw any detections not matched to an active track with default uncounted styling
            for det in detections:
                box_coords = (int(det.x1), int(det.y1), int(det.x2), int(det.y2))
                if box_coords not in rendered_boxes:
                    x1, y1, x2, y2 = box_coords
                    box_color = (0, 180, 255)
                    cv2.rectangle(vis, (x1, y1), (x2, y2), box_color, 2)
                    cv2.putText(
                        vis,
                        f"{det.class_name} {det.confidence:.2f}",
                        (x1, max(20, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        box_color,
                        1,
                    )

            # Flash crossing event banner if occurred on this frame
            if events:
                cv2.rectangle(vis, (w // 2 - 200, 50), (w // 2 + 200, 110), (0, 0, 200), -1)
                cv2.putText(
                    vis,
                    f"COUNT +{len(events)} (Total: {self.counter.total_count})",
                    (w // 2 - 180, 92),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (255, 255, 255),
                    2,
                )

            # Overlay HUD box
            elapsed = max(0.001, time.perf_counter() - (self._start_time_perf or time.perf_counter()))
            fps = self.total_frames_processed / elapsed
            rate = self.counter.total_count * (60.0 / elapsed)

            hud_text = (
                f"Frames: {self.total_frames_processed} | "
                f"Count: {self.counter.total_count} | "
                f"Rate: {rate:.1f}/min | "
                f"FPS: {fps:.1f}"
            )
            cv2.rectangle(vis, (10, 10), (min(w - 10, 560), 45), (0, 0, 0), -1)
            cv2.putText(vis, hud_text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            win_name = f"Chicken Counter - {self.line_id}"
            cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
            if w > 1280:
                cv2.resizeWindow(win_name, 1280, int(1280 * (h / w)))
            cv2.imshow(win_name, vis)
            cv2.waitKey(1)
            return vis
        except Exception as e:
            logger.debug("Error in visual preview: %s", e)
            return None

    def _print_cli_header(self) -> None:
        res_info = ""
        if hasattr(self.source, "cap") and getattr(self.source, "cap", None) is not None:
            try:
                import cv2
                vw = int(self.source.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                vh = int(self.source.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if vw > 0 and vh > 0:
                    res_info = f" [{vw}x{vh}]"
            except Exception:
                pass
        source_desc = f"{self.video_source_type} ({self.video_path}){res_info}" if self.video_path else self.video_source_type
        det_name = self.detector.__class__.__name__
        start_pt = self.counter.line_zone.start
        end_pt = self.counter.line_zone.end
        direction = self.counter.line_zone.direction
        sync_desc = f"ENABLED ({self.api_sync_url})" if self.enable_sync else "DISABLED (Standalone CLI mode)"

        print("\n" + "=" * 74)
        print("          POULTRY COUNTING SYSTEM - EDGE COUNTER SERVICE")
        print("=" * 74)
        print(f"  Line ID:         {self.line_id}")
        print(f"  Video Source:    {source_desc}")
        print(f"  Detector:        {det_name}")
        print(f"  Virtual Line:    ({start_pt[0]:.1f}, {start_pt[1]:.1f}) -> ({end_pt[0]:.1f}, {end_pt[1]:.1f}) [{direction}]")
        print(f"  API Sync:        {sync_desc}")
        print(f"  Outbox Database: {self.db_path}")
        print("=" * 74)
        print("Processing video stream... Press Ctrl+C to stop.\n")
        sys.stdout.flush()

    def _print_cli_summary(self) -> None:
        elapsed = max(0.001, time.perf_counter() - (self._start_time_perf or time.perf_counter()))
        avg_fps = self.total_frames_processed / elapsed
        rate_per_min = self.counter.total_count * (60.0 / elapsed)

        if rate_per_min >= 130.0:
            status = "NORMAL (>= 130/min)"
        elif rate_per_min >= 110.0:
            status = "WARNING (110 - 129/min)"
        else:
            status = "CRITICAL (< 110/min)"

        if self._all_latencies_ms:
            sorted_lat = sorted(self._all_latencies_ms)
            p95_idx = int(0.95 * len(sorted_lat))
            lat_p95 = sorted_lat[min(p95_idx, len(sorted_lat) - 1)]
            lat_avg = sum(self._all_latencies_ms) / len(self._all_latencies_ms)
        else:
            lat_p95 = 0.0
            lat_avg = 0.0

        print("\n\n" + "=" * 74)
        print("                       COUNTER RUN SUMMARY")
        print("=" * 74)
        print(f"  Line ID:                    {self.line_id}")
        print(f"  Video Source:               {self.video_path or self.video_source_type}")
        print(f"  Total Frames Processed:     {self.total_frames_processed}")
        print(f"  Total Chickens Counted:     {self.counter.total_count}")
        print(f"  Total Duration:             {elapsed:.2f} seconds")
        print(f"  Average Processing Speed:   {avg_fps:.1f} FPS")
        print(f"  Avg / p95 Inference Latency:{lat_avg:.2f} ms / {lat_p95:.2f} ms")
        print(f"  Estimated Conveyor Rate:    {rate_per_min:.1f} chickens/min")
        print(f"  Conveyor Line Status:       {status}")
        print(f"  Local Database:             {self.db_path}")
        print("=" * 74 + "\n")
        sys.stdout.flush()

    def _cleanup(self) -> None:
        """Stop background worker, release video source, record telemetry, and flush unsynced records."""
        if not self.cli_display:
            logger.info("Cleaning up counter pipeline resources...")
        self.running = False
        self._stop_event.set()

        try:
            self.source.stop()
        except Exception as e:
            logger.warning("Error stopping video source: %s", e)

        if self.show_window:
            try:
                import cv2
                cv2.destroyAllWindows()
            except Exception:
                pass

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

        # Flush any remaining items in outbox before exit (only if sync enabled)
        if self.enable_sync and self.dispatcher is not None:
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

        if not self.cli_display:
            logger.info(
                "Counter service stopped. Frames: %d, Total counted: %d",
                self.total_frames_processed,
                self.counter.total_count,
            )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command line arguments with environment variable fallbacks."""
    parser = argparse.ArgumentParser(
        description="Edge Poultry Counter Service - Process real video and count chickens in CLI"
    )
    parser.add_argument(
        "--video",
        "-v",
        default=os.getenv("VIDEO_PATH", ""),
        help="Path to video file (MP4, AVI, MKV). Automatically sets source to 'file'.",
    )
    parser.add_argument(
        "--source",
        default=os.getenv("VIDEO_SOURCE_TYPE", "synthetic"),
        help="Video source type: 'synthetic', 'file', or 'rtsp' (default: synthetic)",
    )
    parser.add_argument(
        "--line-id",
        default=os.getenv("LINE_ID", "lineA"),
        help="Conveyor line identifier (default: lineA)",
    )
    parser.add_argument(
        "--model",
        "-m",
        default=os.getenv("MODEL_PATH", ""),
        help="Path to ONNX YOLO model file (optional). If not provided, MockDetector or ShackleDetector is used.",
    )
    parser.add_argument(
        "--detector",
        default=os.getenv("DETECTOR_TYPE", "auto"),
        choices=["auto", "shackle", "mock", "onnx"],
        help="Detector engine: 'auto' (smart selection), 'shackle' (industrial poultry shackle line), 'mock' (intensity threshold), 'onnx' (YOLO model)",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=float(os.getenv("CONF_THRESHOLD", "0.7")),
        help="Detector confidence threshold (default: 0.7)",
    )
    parser.add_argument(
        "--intensity",
        type=int,
        default=int(os.getenv("INTENSITY_THRESHOLD", "150")),
        help="Intensity threshold for MockDetector contour segmentation (default: 150)",
    )
    parser.add_argument(
        "--min-area",
        type=float,
        default=float(os.getenv("MIN_AREA", "0.0")),
        help="Minimum contour area for MockDetector (default: 0.0)",
    )
    parser.add_argument(
        "--max-area",
        type=float,
        default=float(os.getenv("MAX_AREA", "0.0")) or None,
        help="Maximum contour area for MockDetector (default: None)",
    )
    parser.add_argument(
        "--min-width",
        type=float,
        default=float(os.getenv("MIN_WIDTH", "10.0")),
        help="Minimum bounding box width for MockDetector (default: 10.0)",
    )
    parser.add_argument(
        "--min-height",
        type=float,
        default=float(os.getenv("MIN_HEIGHT", "10.0")),
        help="Minimum bounding box height for MockDetector (default: 10.0)",
    )
    parser.add_argument(
        "--occupancy-threshold",
        type=float,
        default=float(os.getenv("OCCUPANCY_THRESHOLD", "4.5")),
        help="Carcass occupancy gradient threshold for ShackleDetector to reject empty shackles (default: 4.5)",
    )
    parser.add_argument(
        "--no-occupancy-check",
        action="store_true",
        help="Disable carcass occupancy verification in ShackleDetector (detects all shackles regardless of occupancy)",
    )
    parser.add_argument(
        "--line",
        default=os.getenv("LINE_COORDS", ""),
        help="Virtual crossing line as x1,y1,x2,y2 (e.g. '0,240,640,240')",
    )
    parser.add_argument(
        "--direction",
        default=os.getenv("LINE_DIRECTION") or None,
        choices=["down", "up", "left", "right", "in", "out"],
        help="Line crossing direction (default: down)",
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        default=os.getenv("NO_SYNC", "").lower() in ("1", "true", "yes"),
        help="Disable sync to central API (standalone mode)",
    )
    parser.add_argument(
        "--api-sync-url",
        default=os.getenv("API_SYNC_URL", "http://localhost:8000/api/v1/sync/batch"),
        help="Central API endpoint for outbox sync",
    )
    parser.add_argument(
        "--db-path",
        default=os.getenv("DB_PATH", "counter_outbox.db"),
        help="Path to local SQLite outbox database file",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        default=os.getenv("LOOP_VIDEO", "").lower() in ("1", "true", "yes"),
        help="Loop video continuously instead of stopping at EOF",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=int(os.getenv("MAX_FRAMES", "0")) or None,
        help="Maximum frames to process before stopping",
    )
    parser.add_argument(
        "--target-fps",
        type=float,
        default=float(os.getenv("TARGET_FPS", "0.0")),
        help="Pace playback to target FPS (e.g. 30.0). 0.0 for unthrottled maximum speed.",
    )
    parser.add_argument(
        "--show-window",
        "--gui",
        action="store_true",
        default=os.getenv("SHOW_WINDOW", "").lower() in ("1", "true", "yes"),
        help="Open an OpenCV visual preview window showing detections and line crossing",
    )
    parser.add_argument(
        "--sync-interval",
        type=float,
        default=float(os.getenv("SYNC_INTERVAL_SEC", "5.0")),
        help="Seconds between background sync attempts",
    )
    parser.add_argument(
        "--aggregate-window",
        type=float,
        default=float(os.getenv("AGGREGATE_WINDOW_SEC", "60.0")),
        help="Rolling aggregation window in seconds (default: 60.0)",
    )
    parser.add_argument(
        "--health-interval",
        type=float,
        default=float(os.getenv("HEALTH_INTERVAL_SEC", "10.0")),
        help="Health telemetry recording interval in seconds (default: 10.0)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        default=os.getenv("VERBOSE", "").lower() in ("1", "true", "yes"),
        help="Enable verbose DEBUG logging",
    )

    if argv is None:
        # If running inside pytest or non-cli environment without explicit argv, don't parse sys.argv
        if any("pytest" in str(arg) for arg in sys.argv):
            argv = []
        else:
            argv = sys.argv[1:]

    return parser.parse_args(argv)


def fetch_remote_line_config(
    api_sync_url: str,
    line_id: str,
    timeout: float = 3.0,
) -> dict | None:
    """Fetches line configuration from central API on startup.
    Returns None if unreachable or on error (enabling offline fallback).
    """
    try:
        import httpx
        # Deduce base URL from api_sync_url (e.g., http://host:port/api/v1/sync/batch -> http://host:port/api/v1/lines/{line_id})
        if "/api/v1/" in api_sync_url:
            base_api = api_sync_url.split("/api/v1/")[0] + "/api/v1"
        elif api_sync_url.rstrip("/").endswith("/api/v1"):
            base_api = api_sync_url.rstrip("/")
        else:
            base_api = f"{api_sync_url.rstrip('/')}/api/v1"

        target_url = f"{base_api}/lines/{line_id}"
        resp = httpx.get(target_url, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        logger.warning("Remote line config returned HTTP %s for line %s", resp.status_code, line_id)
        return None
    except Exception as exc:
        logger.info("Could not fetch remote line config (%s). Using local parameters.", exc)
        return None


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Entrypoint reading configuration from CLI arguments or environment variables and running service."""
    args = parse_args(argv)

    log_level = os.getenv("LOG_LEVEL")
    if log_level is None:
        log_level = "DEBUG" if args.verbose else "WARNING"
    else:
        log_level = log_level.upper()

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    enable_sync = not args.no_sync

    # Remote config startup pull
    remote_config = None
    if enable_sync and args.api_sync_url:
        remote_config = fetch_remote_line_config(args.api_sync_url, args.line_id)
        if remote_config:
            if not args.video and remote_config.get("video_url"):
                args.video = remote_config["video_url"]
                logger.info("[RemoteConfig] Applied video source: %s", args.video)
            if not args.line and remote_config.get("line_coords"):
                args.line = remote_config["line_coords"]
                logger.info("[RemoteConfig] Applied line coordinates: %s", args.line)

    if args.direction is None:
        if remote_config and remote_config.get("line_direction"):
            args.direction = remote_config["line_direction"]
            logger.info("[RemoteConfig] Applied line direction: %s", args.direction)
        else:
            args.direction = "down"

    video_source_type = "file" if args.video else args.source

    # Parse line coordinates if provided
    line_coords = None
    if args.line:
        try:
            parts = [float(x.strip()) for x in args.line.split(",")]
            if len(parts) == 4:
                line_coords = (parts[0], parts[1], parts[2], parts[3])
        except Exception as e:
            logger.warning("Could not parse --line '%s': %s", args.line, e)

    # Initialize Detector
    detector = None
    chosen_detector = args.detector.lower()
    if chosen_detector == "auto":
        if args.model:
            chosen_detector = "onnx"
        elif args.video and ("rekaman" in args.video.lower() or args.direction in ("right", "left")):
            chosen_detector = "shackle"
        else:
            chosen_detector = "mock"

    if chosen_detector == "onnx" or args.model:
        try:
            detector = ONNXDetector(model_path=args.model, conf_threshold=args.conf)
            logger.info("Initialized ONNXDetector with model: %s", args.model)
        except Exception as e:
            logger.warning("Failed to load ONNX model '%s': %s. Falling back to ShackleDetector / MockDetector.", args.model, e)
            if args.video and ("rekaman" in args.video.lower() or args.direction in ("right", "left")):
                chosen_detector = "shackle"
            else:
                chosen_detector = "mock"

    if chosen_detector == "shackle":
        detector = ShackleDetector(
            min_confidence=args.conf,
            occupancy_check=not args.no_occupancy_check,
            occupancy_threshold=args.occupancy_threshold,
        )
        logger.info("Initialized ShackleDetector for industrial shackle conveyor line (occupancy_check=%s, thresh=%.1f)", not args.no_occupancy_check, args.occupancy_threshold)
    elif chosen_detector == "mock" or detector is None:
        detector = MockDetector(
            min_confidence=args.conf,
            intensity_threshold=args.intensity,
            min_width=args.min_width,
            min_height=args.min_height,
            min_area=args.min_area,
            max_area=args.max_area,
            apply_blur=True if args.video else False,
            morph_open=True if args.video else False,
        )
        logger.info("Initialized MockDetector (thresh=%d, min_w=%.1f, min_h=%.1f)", args.intensity, args.min_width, args.min_height)

    service = CounterService(
        line_id=args.line_id,
        video_source_type=video_source_type,
        video_path=args.video,
        api_sync_url=args.api_sync_url,
        db_path=args.db_path,
        sync_interval_sec=args.sync_interval,
        target_fps=args.target_fps,
        aggregate_window_sec=args.aggregate_window,
        health_interval_sec=args.health_interval,
        detector=detector,
        loop=args.loop,
        line_coords=line_coords,
        line_direction=args.direction,
        enable_sync=enable_sync,
        cli_display=True,
        show_window=args.show_window,
    )

    def handle_shutdown(signum: int, frame: object) -> None:
        logger.info("Received termination signal (%d), stopping...", signum)
        service.stop()

    try:
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)
    except (ValueError, AttributeError):
        pass

    service.run(max_frames=args.max_frames)


if __name__ == "__main__":
    main()
