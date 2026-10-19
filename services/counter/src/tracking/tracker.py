"""Object tracking and virtual line crossing counter implementation."""

from dataclasses import dataclass
from datetime import datetime, timezone

try:
    from src.detection.detector import Detection
except ImportError:
    from services.counter.src.detection.detector import Detection

try:
    from src.contracts import CountEventDTO
except ImportError:
    try:
        from services.counter.src.contracts import CountEventDTO
    except ImportError:
        from shared.contracts import CountEventDTO

__all__ = ["TrackedObject", "VirtualLineZone", "ChickenCounter"]


@dataclass
class TrackedObject:
    """Represents an active or historical object track."""

    track_id: int
    last_anchor: tuple[float, float]
    current_anchor: tuple[float, float]
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    class_name: str = "chicken"
    confidence: float = 0.0
    missed_frames: int = 0
    age: int = 0
    counted: bool = False


class VirtualLineZone:
    """Virtual line zone defining a boundary and crossing direction."""

    def __init__(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        direction: str = "down",
    ) -> None:
        """Initialize virtual line zone.

        Args:
            start: Starting coordinates (x, y) of the line segment.
            end: Ending coordinates (x, y) of the line segment.
            direction: Crossing direction: "down", "up", "left", "right", "in", or "out".
        """
        self.start = (float(start[0]), float(start[1]))
        self.end = (float(end[0]), float(end[1]))
        self.direction = direction.lower()

    def crosses(self, p1: tuple[float, float], p2: tuple[float, float]) -> bool:
        """Check whether movement from p1 to p2 crosses the line segment in configured direction.

        Args:
            p1: Previous anchor point (x, y).
            p2: Current anchor point (x, y).

        Returns:
            True if segment (p1 -> p2) intersects (start -> end) in the active direction.
        """
        x1, y1 = float(p1[0]), float(p1[1])
        x2, y2 = float(p2[0]), float(p2[1])

        dx = x2 - x1
        dy = y2 - y1

        # Check direction of movement
        if self.direction in ("down", "in"):
            if dy <= 0:
                return False
        elif self.direction in ("up", "out"):
            if dy >= 0:
                return False
        elif self.direction == "right":
            if dx <= 0:
                return False
        elif self.direction == "left":
            if dx >= 0:
                return False

        ax, ay = self.start
        bx, by = self.end

        # Line segment vector AB = (bx - ax, by - ay)
        # Movement segment vector CD = (x2 - x1, y2 - y1)
        det = (bx - ax) * dy - (by - ay) * dx
        if abs(det) < 1e-9:
            return False

        t = ((x1 - ax) * dy - (y1 - ay) * dx) / det
        u = ((x1 - ax) * (by - ay) - (y1 - ay) * (bx - ax)) / det

        eps = 1e-6
        # t must lie along segment AB: [0, 1]
        # u must lie along movement segment CD: [0, 1) to count exactly on first cross
        return (-eps <= t <= 1.0 + eps) and (-eps <= u < 1.0)


class ChickenCounter:
    """Associates detections into tracks, detects line crossings, and emits count events."""

    def __init__(
        self,
        line_zone: VirtualLineZone,
        line_id: str = "lineA",
        max_age: int = 30,
        max_distance: float = 60.0,
    ) -> None:
        """Initialize counter with a virtual line zone and tracking thresholds.

        Args:
            line_zone: Virtual line zone for crossing detection.
            line_id: Identifier of the monitored line.
            max_age: Maximum consecutive missed frames before track eviction.
            max_distance: Maximum Euclidean distance in pixels to match detection to track.
        """
        self.line_zone = line_zone
        self.line_id = line_id
        self.max_age = max_age
        self.max_distance = max_distance
        self.total_count = 0
        self.tracks: dict[int, TrackedObject] = {}
        self.counted_track_ids: set[int] = set()
        self._next_track_id = 1

    def update(
        self,
        detections: list[Detection],
        timestamp: float | None = None,
    ) -> list[CountEventDTO]:
        """Update tracker with frame detections, check crossings, and return count events.

        Args:
            detections: List of Detection objects in current frame.
            timestamp: Epoch or frame timestamp float in seconds, or None for current UTC time.

        Returns:
            List of CountEventDTO emitted during this frame update.
        """
        if timestamp is not None:
            try:
                event_ts = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            except (ValueError, OverflowError, OSError):
                event_ts = datetime.now(timezone.utc)
        else:
            event_ts = datetime.now(timezone.utc)

        events: list[CountEventDTO] = []

        # Find closest track-detection pairs within max_distance
        candidates: list[tuple[int, float, int, int]] = []
        for track_id, track in self.tracks.items():
            for det_idx, det in enumerate(detections):
                anchor = det.anchor_bottom_center
                dist = (
                    (track.current_anchor[0] - anchor[0]) ** 2
                    + (track.current_anchor[1] - anchor[1]) ** 2
                ) ** 0.5
                if dist <= self.max_distance:
                    # Prioritize active tracks (missed_frames == 0) over stale tracks (missed_frames > 0)
                    candidates.append((track.missed_frames, dist, track_id, det_idx))

        candidates.sort(key=lambda item: (item[0], item[1]))

        matched_track_ids: set[int] = set()
        matched_det_indices: set[int] = set()
        matches: list[tuple[int, int]] = []

        for _, dist, track_id, det_idx in candidates:
            if track_id not in matched_track_ids and det_idx not in matched_det_indices:
                matched_track_ids.add(track_id)
                matched_det_indices.add(det_idx)
                matches.append((track_id, det_idx))

        # Update matched tracks and check crossing
        for track_id, det_idx in matches:
            track = self.tracks[track_id]
            det = detections[det_idx]
            anchor = det.anchor_bottom_center

            track.last_anchor = track.current_anchor
            track.current_anchor = anchor
            track.bbox = (float(det.x1), float(det.y1), float(det.x2), float(det.y2))
            track.class_name = det.class_name
            track.confidence = det.confidence
            track.missed_frames = 0
            track.age += 1

            if track_id not in self.counted_track_ids and not track.counted:
                if self.line_zone.crosses(track.last_anchor, track.current_anchor):
                    track.counted = True
                    self.counted_track_ids.add(track_id)
                    self.total_count += 1
                    events.append(
                        CountEventDTO(
                            track_id=track_id,
                            ts_utc=event_ts,
                            confidence=det.confidence,
                        )
                    )

        # Register unmatched detections as new tracks
        newly_created_ids: set[int] = set()
        for det_idx, det in enumerate(detections):
            if det_idx not in matched_det_indices:
                new_id = self._next_track_id
                self._next_track_id += 1
                anchor = det.anchor_bottom_center
                self.tracks[new_id] = TrackedObject(
                    track_id=new_id,
                    last_anchor=anchor,
                    current_anchor=anchor,
                    bbox=(float(det.x1), float(det.y1), float(det.x2), float(det.y2)),
                    class_name=det.class_name,
                    confidence=det.confidence,
                    missed_frames=0,
                    age=0,
                    counted=False,
                )
                newly_created_ids.add(new_id)

        # Increment missed frames for unmatched tracks and prune stale ones
        stale_ids: list[int] = []
        for track_id, track in self.tracks.items():
            if track_id not in matched_track_ids and track_id not in newly_created_ids:
                track.missed_frames += 1
                track.age += 1
                max_allowed_missed = min(self.max_age, 3) if track.counted else self.max_age
                if track.missed_frames > max_allowed_missed:
                    stale_ids.append(track_id)

        for track_id in stale_ids:
            del self.tracks[track_id]

        return events
