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
    assert obj.bbox == (0.0, 0.0, 0.0, 0.0)
    assert obj.class_name == "chicken"
    assert obj.confidence == 0.0
    assert obj.missed_frames == 0
    assert obj.age == 0
    assert obj.counted is False


def test_tracked_object_bbox_and_metadata_fields():
    """Verify TrackedObject dataclass holds bbox, class_name, and confidence."""
    obj = TrackedObject(
        track_id=1,
        last_anchor=(100.0, 150.0),
        current_anchor=(100.0, 160.0),
        bbox=(80.0, 120.0, 120.0, 160.0),
        class_name="chicken",
        confidence=0.92,
    )
    assert obj.bbox == (80.0, 120.0, 120.0, 160.0)
    assert obj.class_name == "chicken"
    assert obj.confidence == 0.92


def test_tracker_records_bbox_on_creation_and_update():
    """Verify ChickenCounter.update records bbox, class_name, and confidence on new tracks and matches."""
    line_zone = VirtualLineZone(start=(0, 200), end=(640, 200), direction="down")
    counter = ChickenCounter(line_zone=line_zone)

    # Frame 1: Detection creates new track
    det1 = Detection(
        x1=100.0,
        y1=120.0,
        x2=140.0,
        y2=160.0,
        confidence=0.88,
        class_id=0,
        class_name="chicken",
    )
    counter.update([det1], timestamp=100.0)
    assert len(counter.tracks) == 1
    track = counter.tracks[1]
    assert track.bbox == (100.0, 120.0, 140.0, 160.0)
    assert track.class_name == "chicken"
    assert track.confidence == 0.88
    assert track.counted is False

    # Frame 2: Detection moves and matches track
    det2 = Detection(
        x1=102.0,
        y1=150.0,
        x2=142.0,
        y2=190.0,
        confidence=0.93,
        class_id=0,
        class_name="chicken",
    )
    counter.update([det2], timestamp=100.033)
    track = counter.tracks[1]
    assert track.bbox == (102.0, 150.0, 142.0, 190.0)
    assert track.class_name == "chicken"
    assert track.confidence == 0.93
    assert track.counted is False


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


def test_empty_shackle_not_counted_during_tracking():
    """Verify that an empty shackle traversing across the count line does not trigger a false count."""
    import os
    import cv2
    import pytest
    from services.counter.src.detection.detector import ShackleDetector

    video_path = "samples/Rekaman_2.MOV"
    if not os.path.exists(video_path):
        pytest.skip(f"Video file {video_path} not found")

    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 3020)

    line_zone = VirtualLineZone(
        start=(960.0, 216.0), end=(960.0, 972.0), direction="right"
    )
    counter = ChickenCounter(line_zone=line_zone, line_id="lineA", max_distance=96.0)
    detector = ShackleDetector(occupancy_check=True)

    counted_events = []
    # Process frames 3020 to 3120 spanning the empty shackle traversal across virtual line
    for f in range(3020, 3120):
        ret, frame = cap.read()
        if not ret:
            break
        detections = detector.predict(frame)
        events = counter.update(detections)
        if events:
            for ev in events:
                counted_events.append((f, ev))

    cap.release()

    # In frames 3020..3120:
    # 2 real chickens cross at frame ~3027 and ~3051
    # 1 empty shackle passes line at frame ~3078 (must NOT be counted)
    # 1 real chicken crosses at frame ~3103
    # Exactly 3 chickens should be counted, not 4
    assert len(counted_events) == 3
    assert counter.total_count == 3
    counted_frames = [item[0] for item in counted_events]
    # Verify no count happened around frame 3078
    assert not any(3070 <= f <= 3085 for f in counted_frames)


def test_active_track_priority_prevents_stale_track_theft():
    """Verify active tracks take precedence over stale tracks even if the stale track is closer."""
    # Line zone at x=300 moving right
    line_zone = VirtualLineZone(start=(300.0, 50.0), end=(300.0, 450.0), direction="right")
    counter = ChickenCounter(line_zone=line_zone, line_id="lineA", max_distance=60.0)

    # Frame 1: Chicken 1 at 290, Chicken 2 at 190
    counter.update([
        Detection(x1=270, y1=100, x2=310, y2=200, confidence=0.9, class_id=0, class_name="chicken"),
        Detection(x1=170, y1=100, x2=210, y2=200, confidence=0.9, class_id=0, class_name="chicken"),
    ])
    assert 1 in counter.tracks and 2 in counter.tracks

    # Frame 2: Chicken 1 crosses to 310 (counted!), Chicken 2 moves to 220
    events1 = counter.update([
        Detection(x1=290, y1=100, x2=330, y2=200, confidence=0.9, class_id=0, class_name="chicken"),
        Detection(x1=200, y1=100, x2=240, y2=200, confidence=0.9, class_id=0, class_name="chicken"),
    ])
    assert len(events1) == 1
    assert counter.tracks[1].counted is True

    # Frame 3: Chicken 1 is missed! Chicken 2 moves to 250
    counter.update([
        Detection(x1=230, y1=100, x2=270, y2=200, confidence=0.9, class_id=0, class_name="chicken"),
    ])
    assert counter.tracks[2].current_anchor == (250.0, 200.0)
    assert counter.tracks[2].missed_frames == 0
    assert counter.tracks[1].missed_frames == 1

    # Frame 4: Chicken 2 moves to 280. Chicken 1 still missed at 310 (missed_frames=2)
    counter.update([
        Detection(x1=260, y1=100, x2=300, y2=200, confidence=0.9, class_id=0, class_name="chicken"),
    ])
    assert counter.tracks[2].current_anchor == (280.0, 200.0)
    assert counter.tracks[1].missed_frames == 2

    # Frame 5: Chicken 2 moves to 308 (crosses line!).
    # Distance to Chicken 1 (at 310) is only 2px!
    # Distance to Chicken 2 (at 280) is 28px!
    # Under old logic, stale Track 1 (dist 2px) stole the detection and Chicken 2 was never counted.
    # Under active track priority, active Track 2 gets the detection and is counted!
    events2 = counter.update([
        Detection(x1=288, y1=100, x2=328, y2=200, confidence=0.9, class_id=0, class_name="chicken"),
    ])
    assert len(events2) == 1
    assert events2[0].track_id == 2
    assert counter.total_count == 2
    assert counter.tracks[2].counted is True


