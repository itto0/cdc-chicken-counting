"""Unit tests for object tracking and virtual line zone crossing counter."""

from datetime import datetime, timezone

from services.counter.src.detection.detector import Detection
from services.counter.src.tracking.tracker import (
    ChickenCounter,
    TrackedObject,
    VirtualLineZone,
)
from shared.contracts import CountEventDTO


def test_tracked_object_dataclass_fields():
    """Verify TrackedObject dataclass structure and default values."""
    obj = TrackedObject(
        track_id=1,
        last_anchor=(100.0, 150.0),
        current_anchor=(100.0, 160.0),
    )
    assert obj.track_id == 1
    assert obj.last_anchor == (100.0, 150.0)
    assert obj.current_anchor == (100.0, 160.0)
    assert obj.missed_frames == 0
    assert obj.age == 0
    assert obj.counted is False


def test_line_crossing_increments_count_once():
    """Verify chicken moving downwards across horizontal line increments count once."""
    # Horizontal line crossing downwards across y=200
    line_zone = VirtualLineZone(start=(0, 200), end=(640, 200), direction="down")
    counter = ChickenCounter(line_zone=line_zone, line_id="lineA")

    # Frame 1: chicken above line (anchor bottom center at y=180)
    det1 = Detection(
        x1=280,
        y1=140,
        x2=320,
        y2=180,
        confidence=0.95,
        class_id=0,
        class_name="chicken",
    )
    events1 = counter.update([det1], timestamp=1000.0)
    assert len(events1) == 0
    assert counter.total_count == 0

    # Frame 2: chicken crosses line (anchor bottom center at y=220)
    det2 = Detection(
        x1=280,
        y1=180,
        x2=320,
        y2=220,
        confidence=0.96,
        class_id=0,
        class_name="chicken",
    )
    events2 = counter.update([det2], timestamp=1000.033)
    assert len(events2) == 1
    assert counter.total_count == 1
    assert events2[0].confidence == 0.96
    assert events2[0].track_id == 1
    assert isinstance(events2[0], CountEventDTO)
    assert isinstance(events2[0].ts_utc, datetime)

    # Frame 3: chicken continues downwards (no double count)
    det3 = Detection(
        x1=280,
        y1=220,
        x2=320,
        y2=260,
        confidence=0.94,
        class_id=0,
        class_name="chicken",
    )
    events3 = counter.update([det3], timestamp=1000.066)
    assert len(events3) == 0
    assert counter.total_count == 1


def test_double_count_prevention_vibrating_across_line():
    """Verify that a tracked chicken vibrating back and forth across line is only counted once."""
    line_zone = VirtualLineZone(start=(0, 200), end=(640, 200), direction="down")
    counter = ChickenCounter(line_zone=line_zone, line_id="lineA")

    # Frame 1: chicken above line (y=180)
    det1 = Detection(
        x1=280,
        y1=140,
        x2=320,
        y2=180,
        confidence=0.95,
        class_id=0,
        class_name="chicken",
    )
    counter.update([det1], timestamp=1000.0)
    assert counter.total_count == 0

    # Frame 2: crosses downwards to y=220 -> counted
    det2 = Detection(
        x1=280,
        y1=180,
        x2=320,
        y2=220,
        confidence=0.95,
        class_id=0,
        class_name="chicken",
    )
    events2 = counter.update([det2], timestamp=1000.033)
    assert len(events2) == 1
    assert counter.total_count == 1

    # Frame 3: vibrates back up across line to y=190 -> should NOT count
    det3 = Detection(
        x1=280,
        y1=150,
        x2=320,
        y2=190,
        confidence=0.95,
        class_id=0,
        class_name="chicken",
    )
    events3 = counter.update([det3], timestamp=1000.066)
    assert len(events3) == 0
    assert counter.total_count == 1

    # Frame 4: crosses down again to y=220 -> should NOT double count
    det4 = Detection(
        x1=280,
        y1=180,
        x2=320,
        y2=220,
        confidence=0.95,
        class_id=0,
        class_name="chicken",
    )
    events4 = counter.update([det4], timestamp=1000.100)
    assert len(events4) == 0
    assert counter.total_count == 1


def test_reverse_direction_does_not_count():
    """Verify upward crossing does not increment count when direction is down."""
    line_zone = VirtualLineZone(start=(0, 200), end=(640, 200), direction="down")
    counter = ChickenCounter(line_zone=line_zone, line_id="lineA")

    # Frame 1: chicken starts below line (anchor at y=230)
    det1 = Detection(
        x1=280,
        y1=190,
        x2=320,
        y2=230,
        confidence=0.95,
        class_id=0,
        class_name="chicken",
    )
    events1 = counter.update([det1], timestamp=1000.0)
    assert len(events1) == 0
    assert counter.total_count == 0

    # Frame 2: chicken moves upwards across line to y=170
    det2 = Detection(
        x1=280,
        y1=130,
        x2=320,
        y2=170,
        confidence=0.95,
        class_id=0,
        class_name="chicken",
    )
    events2 = counter.update([det2], timestamp=1000.033)
    assert len(events2) == 0
    assert counter.total_count == 0


def test_upward_direction_counts_when_configured():
    """Verify upward crossing is counted when direction is configured as 'up'."""
    line_zone = VirtualLineZone(start=(0, 200), end=(640, 200), direction="up")
    counter = ChickenCounter(line_zone=line_zone, line_id="lineA")

    # Frame 1: chicken below line (y=230)
    det1 = Detection(
        x1=280,
        y1=190,
        x2=320,
        y2=230,
        confidence=0.95,
        class_id=0,
        class_name="chicken",
    )
    counter.update([det1], timestamp=1000.0)
    assert counter.total_count == 0

    # Frame 2: chicken moves upwards across line to y=170
    det2 = Detection(
        x1=280,
        y1=130,
        x2=320,
        y2=170,
        confidence=0.95,
        class_id=0,
        class_name="chicken",
    )
    events2 = counter.update([det2], timestamp=1000.033)
    assert len(events2) == 1
    assert counter.total_count == 1


def test_multiple_concurrent_chickens_crossing():
    """Verify multiple concurrent chickens are tracked and counted independently."""
    line_zone = VirtualLineZone(start=(0, 200), end=(640, 200), direction="down")
    counter = ChickenCounter(line_zone=line_zone, line_id="lineA")

    # Frame 1: two chickens above line, separated horizontally
    # Chicken A at x=100, y=180
    det_a1 = Detection(
        x1=80, y1=140, x2=120, y2=180, confidence=0.92, class_id=0, class_name="chicken"
    )
    # Chicken B at x=400, y=180
    det_b1 = Detection(
        x1=380,
        y1=140,
        x2=420,
        y2=180,
        confidence=0.94,
        class_id=0,
        class_name="chicken",
    )

    events1 = counter.update([det_a1, det_b1], timestamp=1000.0)
    assert len(events1) == 0
    assert counter.total_count == 0
    assert len(counter.tracks) == 2

    # Frame 2: both cross line downwards
    det_a2 = Detection(
        x1=80, y1=180, x2=120, y2=220, confidence=0.93, class_id=0, class_name="chicken"
    )
    det_b2 = Detection(
        x1=380,
        y1=180,
        x2=420,
        y2=220,
        confidence=0.95,
        class_id=0,
        class_name="chicken",
    )

    events2 = counter.update([det_a2, det_b2], timestamp=1000.033)
    assert len(events2) == 2
    assert counter.total_count == 2
    track_ids = {e.track_id for e in events2}
    assert len(track_ids) == 2

    # Frame 3: both continue downwards
    det_a3 = Detection(
        x1=80, y1=220, x2=120, y2=260, confidence=0.91, class_id=0, class_name="chicken"
    )
    det_b3 = Detection(
        x1=380,
        y1=220,
        x2=420,
        y2=260,
        confidence=0.93,
        class_id=0,
        class_name="chicken",
    )

    events3 = counter.update([det_a3, det_b3], timestamp=1000.066)
    assert len(events3) == 0
    assert counter.total_count == 2


def test_track_cleanup_of_stale_tracks():
    """Verify tracks are purged after exceeding max_age missed frames."""
    line_zone = VirtualLineZone(start=(0, 200), end=(640, 200), direction="down")
    counter = ChickenCounter(line_zone=line_zone, line_id="lineA", max_age=5)

    # Frame 1: chicken appears
    det = Detection(
        x1=280,
        y1=140,
        x2=320,
        y2=180,
        confidence=0.95,
        class_id=0,
        class_name="chicken",
    )
    counter.update([det], timestamp=1000.0)
    assert len(counter.tracks) == 1

    # Next 5 frames: no detections (missed_frames = 1, 2, 3, 4, 5)
    for i in range(1, 6):
        counter.update([], timestamp=1000.0 + i * 0.033)
        assert len(counter.tracks) == 1

    # 6th frame without detection: exceeds max_age=5, track is purged
    counter.update([], timestamp=1000.200)
    assert len(counter.tracks) == 0


def test_crossing_outside_segment_bounds_not_counted():
    """Verify crossing that occurs outside the virtual line segment is ignored."""
    # Line only spans x from 100 to 300
    line_zone = VirtualLineZone(start=(100, 200), end=(300, 200), direction="down")
    counter = ChickenCounter(line_zone=line_zone, line_id="lineA")

    # Chicken crosses at x=500 (outside x in [100, 300])
    det1 = Detection(
        x1=480,
        y1=140,
        x2=520,
        y2=180,
        confidence=0.95,
        class_id=0,
        class_name="chicken",
    )
    counter.update([det1], timestamp=1000.0)

    det2 = Detection(
        x1=480,
        y1=180,
        x2=520,
        y2=220,
        confidence=0.95,
        class_id=0,
        class_name="chicken",
    )
    events = counter.update([det2], timestamp=1000.033)
    assert len(events) == 0
    assert counter.total_count == 0


def test_vertical_line_crossing():
    """Verify vertical line zone crossing with direction='right'."""
    line_zone = VirtualLineZone(start=(300, 0), end=(300, 480), direction="right")
    counter = ChickenCounter(line_zone=line_zone, line_id="lineB")

    # Frame 1: chicken to the left of x=300 (anchor x=280)
    det1 = Detection(
        x1=260,
        y1=100,
        x2=300,
        y2=140,
        confidence=0.95,
        class_id=0,
        class_name="chicken",
    )
    counter.update([det1], timestamp=1000.0)
    assert counter.total_count == 0

    # Frame 2: crosses to the right of x=300 (anchor x=320)
    det2 = Detection(
        x1=300,
        y1=100,
        x2=340,
        y2=140,
        confidence=0.96,
        class_id=0,
        class_name="chicken",
    )
    events = counter.update([det2], timestamp=1000.033)
    assert len(events) == 1
    assert counter.total_count == 1
    assert events[0].track_id == 1


def test_vertical_line_crossing_left():
    """Verify vertical line zone crossing with direction='left'."""
    line_zone = VirtualLineZone(start=(300, 0), end=(300, 480), direction="left")
    counter = ChickenCounter(line_zone=line_zone, line_id="lineB")

    # Frame 1: chicken to the right of x=300 (anchor x=320)
    det1 = Detection(
        x1=300,
        y1=100,
        x2=340,
        y2=140,
        confidence=0.95,
        class_id=0,
        class_name="chicken",
    )
    counter.update([det1], timestamp=1000.0)
    assert counter.total_count == 0

    # Frame 2: crosses to the left of x=300 (anchor x=280)
    det2 = Detection(
        x1=260,
        y1=100,
        x2=300,
        y2=140,
        confidence=0.96,
        class_id=0,
        class_name="chicken",
    )
    events = counter.update([det2], timestamp=1000.033)
    assert len(events) == 1
    assert counter.total_count == 1


def test_update_without_timestamp_uses_utc_now():
    """Verify update without timestamp generates a valid UTC datetime CountEventDTO."""
    line_zone = VirtualLineZone(start=(0, 200), end=(640, 200), direction="down")
    counter = ChickenCounter(line_zone=line_zone, line_id="lineA")

    det1 = Detection(
        x1=280,
        y1=140,
        x2=320,
        y2=180,
        confidence=0.95,
        class_id=0,
        class_name="chicken",
    )
    counter.update([det1])

    det2 = Detection(
        x1=280,
        y1=180,
        x2=320,
        y2=220,
        confidence=0.97,
        class_id=0,
        class_name="chicken",
    )
    before_call = datetime.now(timezone.utc)
    events = counter.update([det2])
    after_call = datetime.now(timezone.utc)

    assert len(events) == 1
    event = events[0]
    assert before_call <= event.ts_utc <= after_call


def test_empty_detections_does_not_crash():
    """Verify calling update on empty tracks and empty detections operates safely."""
    line_zone = VirtualLineZone(start=(0, 200), end=(640, 200), direction="down")
    counter = ChickenCounter(line_zone=line_zone)

    events = counter.update([])
    assert events == []
    assert counter.total_count == 0
    assert len(counter.tracks) == 0


def test_parallel_or_stationary_movement_returns_false():
    """Verify parallel or zero-movement trajectories do not trigger line crossing."""
    line_zone = VirtualLineZone(start=(0, 200), end=(640, 200), direction="down")

    # Stationary point
    assert line_zone.crosses((300, 180), (300, 180)) is False

    # Parallel movement along x
    assert line_zone.crosses((100, 200), (300, 200)) is False

    # Zero-length line
    zero_line = VirtualLineZone(start=(200, 200), end=(200, 200), direction="down")
    assert zero_line.crosses((200, 180), (200, 220)) is False


def test_association_distance_competition():
    """Verify closest detection matches existing track, while distant detection spawns new track."""
    line_zone = VirtualLineZone(start=(0, 200), end=(640, 200), direction="down")
    counter = ChickenCounter(line_zone=line_zone, max_distance=50.0)

    # Frame 1: chicken at (100, 150)
    det1 = Detection(
        x1=80, y1=120, x2=120, y2=150, confidence=0.9, class_id=0, class_name="chicken"
    )
    counter.update([det1])
    assert len(counter.tracks) == 1
    assert 1 in counter.tracks

    # Frame 2: two detections
    # Det A is 10px away from track 1 (100, 160)
    det_a = Detection(
        x1=80, y1=130, x2=120, y2=160, confidence=0.9, class_id=0, class_name="chicken"
    )
    # Det B is 100px away from track 1 (200, 150) - exceeds max_distance 50.0
    det_b = Detection(
        x1=180, y1=120, x2=220, y2=150, confidence=0.9, class_id=0, class_name="chicken"
    )

    events = counter.update([det_a, det_b])
    assert len(events) == 0
    assert len(counter.tracks) == 2
    # Track 1 updated with det_a
    assert counter.tracks[1].current_anchor == det_a.anchor_bottom_center
    # Track 2 created with det_b
    assert counter.tracks[2].current_anchor == det_b.anchor_bottom_center
