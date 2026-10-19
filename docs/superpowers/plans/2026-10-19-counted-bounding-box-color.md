# Counted Bounding Box Color Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change chicken bounding box colors dynamically when counted (Orange for approaching/uncounted, Bright Green for crossing, Green with `[COUNTED]` label for already counted) across both Edge Counter preview window and Web Live Stream.

**Architecture:** Extend `TrackedObject` in the edge counter tracker to store bounding box geometry, class, and confidence so `_render_window_frame` renders tracks based on their exact `counted` status. Update Web API `FrameGenerator` to color bounding boxes based on conveyor crossing geometry relative to the virtual line.

**Tech Stack:** Python 3.14, OpenCV (cv2), NumPy, FastAPI, Pytest.

## Global Constraints

- Python environment runner command: `py -m pytest`
- Color standards (BGR):
  - Approaching / Uncounted: `(0, 180, 255)` (Orange)
  - Crossing virtual line: `(0, 255, 0)` (Bright Green)
  - Counted: `(0, 220, 0)` (Green)
- Label tags: Counted objects MUST include `[COUNTED]` in the text label.
- Stale tracks (`missed_frames > 0`) must not render bounding boxes to avoid drawing ghosts.

---

### Task 1: Extend Tracker Data Structures and State Tracking

**Files:**
- Modify: `services/counter/src/tracking/tracker.py:20-40, 169-208`
- Test: `services/counter/tests/test_tracking.py`

**Interfaces:**
- Consumes: `Detection` dataclass (`x1`, `y1`, `x2`, `y2`, `confidence`, `class_name`, `anchor_bottom_center`).
- Produces: `TrackedObject` dataclass with fields `bbox: tuple[float, float, float, float]`, `class_name: str`, `confidence: float`, and `counted: bool`.

- [ ] **Step 1: Write the failing tests in `test_tracking.py`**

Add tests to `services/counter/tests/test_tracking.py` checking that `TrackedObject` stores `bbox`, `class_name`, and `confidence`, and that `ChickenCounter.update` populates and updates them properly for both new tracks and matched tracks.

```python
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
    assert track.confidence == 0.93
    assert track.counted is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/counter/tests/test_tracking.py -k "test_tracked_object_bbox_and_metadata_fields or test_tracker_records_bbox_on_creation_and_update" -v`
Expected: FAIL (Unexpected keyword argument `bbox` in `TrackedObject`).

- [ ] **Step 3: Implement `bbox`, `class_name`, and `confidence` in `tracker.py`**

In `services/counter/src/tracking/tracker.py`:
1. Update `TrackedObject` dataclass:
```python
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
```

2. In `ChickenCounter.update`, update matched tracks:
```python
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
```

3. In `ChickenCounter.update`, register new tracks:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -m pytest services/counter/tests/test_tracking.py -v`
Expected: PASS (all tests in `test_tracking.py` pass).

- [ ] **Step 5: Commit changes**

```bash
git add services/counter/src/tracking/tracker.py services/counter/tests/test_tracking.py
git commit -m "feat(counter): store bbox and metadata on TrackedObject"
```

---

### Task 2: Update Counter Service Desktop Preview Rendering

**Files:**
- Modify: `services/counter/main.py:454-545`
- Test: `services/counter/tests/test_main.py`

**Interfaces:**
- Consumes: `self.counter.tracks.values()` with `track.counted`, `track.bbox`, `track.confidence`, `track.class_name`, `track.missed_frames`.
- Produces: `_render_window_frame(frame, detections, events)` returning `vis` annotated frame where uncounted tracks have BGR `(0, 180, 255)`, counted tracks have BGR `(0, 220, 0)` with `[COUNTED]` in text label.

- [ ] **Step 1: Write the failing tests in `test_main.py`**

Add tests to `services/counter/tests/test_main.py` testing `_render_window_frame`:
```python
def test_render_window_frame_bounding_box_colors(tmp_path):
    """Verify _render_window_frame colors uncounted tracks orange and counted tracks green."""
    import numpy as np
    from unittest.mock import patch
    from services.counter.src.detection.detector import Detection
    from services.counter.src.tracking.tracker import TrackedObject

    db_file = str(tmp_path / "test_render.db")
    service = CounterService(
        line_id="lineRender",
        video_source_type="synthetic",
        db_path=db_file,
    )

    # Track 1: uncounted
    track1 = TrackedObject(
        track_id=1,
        last_anchor=(100.0, 150.0),
        current_anchor=(100.0, 150.0),
        bbox=(50.0, 50.0, 150.0, 150.0),
        class_name="chicken",
        confidence=0.91,
        counted=False,
        missed_frames=0,
    )
    # Track 2: counted
    track2 = TrackedObject(
        track_id=2,
        last_anchor=(300.0, 350.0),
        current_anchor=(300.0, 350.0),
        bbox=(250.0, 250.0, 350.0, 350.0),
        class_name="chicken",
        confidence=0.95,
        counted=True,
        missed_frames=0,
    )
    service.counter.tracks = {1: track1, 2: track2}

    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    with patch("cv2.imshow"), patch("cv2.namedWindow"), patch("cv2.resizeWindow"), patch("cv2.waitKey"):
        vis = service._render_window_frame(dummy_frame, detections=[], events=[])

    assert vis is not None
    # Track 1 border at (x=50, y=50) should be Orange (BGR: 0, 180, 255)
    # Pixel on boundary:
    assert tuple(vis[50, 100]) == (0, 180, 255)
    # Track 2 border at (x=250, y=250) should be Green (BGR: 0, 220, 0)
    assert tuple(vis[250, 300]) == (0, 220, 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/counter/tests/test_main.py -k "test_render_window_frame_bounding_box_colors" -v`
Expected: FAIL (`vis` is None or colors mismatch).

- [ ] **Step 3: Implement track-based rendering with counted status in `services/counter/main.py`**

Update `_render_window_frame` in `services/counter/main.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -m pytest services/counter/tests/test_main.py -v`
Expected: PASS (all tests pass).

- [ ] **Step 5: Commit changes**

```bash
git add services/counter/main.py services/counter/tests/test_main.py
git commit -m "feat(counter): render counted bounding boxes in green with tag"
```

---

### Task 3: Update Web API Preview Stream Bounding Box Colors

**Files:**
- Modify: `services/api/src/services/preview.py:122-141, 193-197`
- Test: `services/api/tests/test_preview_api.py`

**Interfaces:**
- Consumes: Chicken coordinates on conveyor (`rcx` for real video, `x_pos` for synthetic frame), `mid_x = 320`.
- Produces: JPEG frames containing:
  - Approaching chicken (`rcx < mid_x - 18` or `x_pos < 300`): Orange `(0, 180, 255)`.
  - Crossing chicken (`abs(rcx - mid_x) <= 18` or `abs(x_pos - 320) <= 20`): Bright Green `(0, 255, 0)`.
  - Counted chicken (`rcx > mid_x + 18` or `x_pos > 340`): Green `(0, 220, 0)` with `[COUNTED]` label.

- [ ] **Step 1: Write the failing tests in `test_preview_api.py`**

Add tests to `services/api/tests/test_preview_api.py`:
```python
def test_synthetic_preview_frame_bounding_box_colors():
    """Verify synthetic preview frame generates orange, bright green, and counted green boxes."""
    # Frame 0: x_pos = (0 * 15) % 500 + 70 = 70 (< 300: Approaching/Uncounted)
    frame_uncounted_bytes = FrameGenerator.generate_jpeg_frame("test-line", 0)
    arr0 = np.frombuffer(frame_uncounted_bytes, dtype=np.uint8)
    img0 = cv2.imdecode(arr0, cv2.IMREAD_COLOR)
    # Box rectangle at x_pos=70 is from x=40 to x=100, y=190 to y=310.
    # BGR color for uncounted is (0, 180, 255) (Orange)
    # Check top horizontal border of the box at (y=190, x=70)
    assert img0[190, 70][0] < 50  # Blue channel low
    assert img0[190, 70][1] > 140  # Green channel ~180
    assert img0[190, 70][2] > 200  # Red channel ~255

    # Frame 17: x_pos = (17 * 15) % 500 + 70 = 325 (Crossing virtual line at 320)
    frame_crossing_bytes = FrameGenerator.generate_jpeg_frame("test-line", 17)
    arr17 = np.frombuffer(frame_crossing_bytes, dtype=np.uint8)
    img17 = cv2.imdecode(arr17, cv2.IMREAD_COLOR)
    # BGR color for crossing is (0, 255, 0) (Bright green)
    assert img17[190, 325][0] < 50  # Blue channel low
    assert img17[190, 325][1] > 220  # Green channel high
    assert img17[190, 325][2] < 50  # Red channel low

    # Frame 21: x_pos = (21 * 15) % 500 + 70 = 385 (> 340: Counted)
    frame_counted_bytes = FrameGenerator.generate_jpeg_frame("test-line", 21)
    arr21 = np.frombuffer(frame_counted_bytes, dtype=np.uint8)
    img21 = cv2.imdecode(arr21, cv2.IMREAD_COLOR)
    # BGR color for counted is (0, 220, 0) (Green)
    assert img21[190, 385][0] < 50  # Blue channel low
    assert img21[190, 385][1] > 180  # Green channel ~220
    assert img21[190, 385][2] < 50  # Red channel low
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -m pytest services/api/tests/test_preview_api.py -k "test_synthetic_preview_frame_bounding_box_colors" -v`
Expected: FAIL (assertion error on color values).

- [ ] **Step 3: Update `services/api/src/services/preview.py`**

In `services/api/src/services/preview.py`:
1. In `generate_jpeg_frame` for real video processing (lines 122-130):
```python
                    is_crossing = abs(rcx - mid_x) <= 18
                    if is_crossing:
                        line_active = True
                        box_color = (0, 255, 0)
                        label = "COUNTING (90%)"
                    elif rcx > mid_x + 18:
                        box_color = (0, 220, 0)
                        label = "Ayam [COUNTED] (90%)"
                    else:
                        box_color = (0, 180, 255)
                        label = "Ayam (90%)"
```

2. In `generate_jpeg_frame` for synthetic fallback (lines 193-197):
```python
        # Animated shackle / chicken moving across
        x_pos = int((safe_frame_num * 15) % 500 + 70)
        mid_x = 320
        if abs(x_pos - mid_x) <= 20:
            box_color = (0, 255, 0)
            label = f"Chicken #{(safe_frame_num // 33) + 1} COUNTING (98%)"
        elif x_pos > mid_x + 20:
            box_color = (0, 220, 0)
            label = f"Chicken #{(safe_frame_num // 33) + 1} [COUNTED] (98%)"
        else:
            box_color = (0, 180, 255)
            label = f"Chicken #{(safe_frame_num // 33) + 1} (98%)"

        cv2.rectangle(img, (x_pos - 30, 190), (x_pos + 30, 310), box_color, 2)
        cv2.putText(img, label, (x_pos - 35, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.4, box_color, 1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -m pytest services/api/tests/test_preview_api.py -v`
Expected: PASS (all tests pass).

- [ ] **Step 5: Commit changes**

```bash
git add services/api/src/services/preview.py services/api/tests/test_preview_api.py
git commit -m "feat(api): update preview stream bounding box colors based on crossing position"
```

---

### Task 4: Full System Verification and Regression Testing

**Files:**
- Test: `services/counter/tests/`
- Test: `services/api/tests/`

**Interfaces:**
- Validates all counter and API preview tests pass together without regressions.

- [ ] **Step 1: Run all tests in `services/counter/tests`**

Run: `py -m pytest services/counter/tests -v`
Expected: PASS (All tests pass with 0 failures).

- [ ] **Step 2: Run all tests in `services/api/tests`**

Run: `py -m pytest services/api/tests -v`
Expected: PASS (All tests pass with 0 failures).

- [ ] **Step 3: Run git status and diff check to confirm clean state**

Run: `git status`
Expected: Working tree clean or only tracked changes.
