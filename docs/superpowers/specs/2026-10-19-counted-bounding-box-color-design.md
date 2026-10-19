# Counted Bounding Box Color Design

## 1. Overview
In the current system, bounding boxes for detected chickens are rendered with a static green color in the Counter Service desktop window (`services/counter/main.py`), and in the Web Live Preview (`services/api/src/services/preview.py`) they toggle between yellow/orange and bright green only during line intersection.

This design introduces a dynamic state-based bounding box visualization:
- **Uncounted / Approaching chickens:** Rendered in **Orange/Yellow** (`BGR: (0, 180, 255)`).
- **Crossing line chickens (web preview):** Highlighted in **Bright Green** (`BGR: (0, 255, 0)`) with `COUNTING (90%)` label.
- **Already Counted chickens:** Rendered in **Green** (`BGR: (0, 220, 0)`) with an explicit `[COUNTED]` tag in the label.

This provides immediate visual confirmation to operators and viewers on both desktop and web feeds that a bird has been counted.

---

## 2. Architecture & Component Changes

### 2.1 Tracker Data Structures (`services/counter/src/tracking/tracker.py`)
Enhance `TrackedObject` to store the latest bounding box coordinates, class name, and confidence:

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

In `ChickenCounter.update(detections, timestamp)`:
- When a detection is matched with an existing track:
  - Update `track.bbox = (det.x1, det.y1, det.x2, det.y2)`
  - Update `track.class_name = det.class_name`
  - Update `track.confidence = det.confidence`
- When a new track is initialized:
  - Populate `bbox`, `class_name`, and `confidence` from the detection.

### 2.2 Counter Service Preview Window (`services/counter/main.py`)
In `CounterService._render_window_frame(frame, detections, events)`:
- Instead of iterating blindly over unassociated `detections`, render active tracks from `self.counter.tracks.values()` where `track.missed_frames == 0`:
  - **Counted (`track.counted == True`):**
    - Color: `(0, 220, 0)` (Green in BGR)
    - Label: `f"{track.class_name} #{track.track_id} {track.confidence:.2f} [COUNTED]"`
  - **Uncounted (`track.counted == False`):**
    - Color: `(0, 180, 255)` (Orange in BGR)
    - Label: `f"{track.class_name} #{track.track_id} {track.confidence:.2f}"`
- If there are detections in the current frame not matched to any active track, render them with default uncounted styling (Orange, no track ID).
- Retain track anchor circle in Yellow `(0, 255, 255)` for spatial tracking alignment.

### 2.3 Web API Live MJPEG Preview (`services/api/src/services/preview.py`)
In `FrameGenerator.generate_frame(line_id, video_path)`:
The virtual line sits at `mid_x = 320` with conveyor moving left-to-right (`direction="right"`):
1. **Real Video Detection Simulation:**
   - For each detected chicken center `cx` (scaled to `rcx`):
     - `rcx < mid_x - 18` (Before line):
       - `box_color = (0, 180, 255)` (Orange)
       - `label = "Ayam (90%)"`
     - `abs(rcx - mid_x) <= 18` (Crossing line):
       - `line_active = True`
       - `box_color = (0, 255, 0)` (Bright Green)
       - `label = "COUNTING (90%)"`
     - `rcx > mid_x + 18` (Past line / Counted):
       - `box_color = (0, 220, 0)` (Green)
       - `label = "Ayam [COUNTED] (90%)"`
2. **Synthetic Fallback Generation:**
   - In synthetic chicken movement loop (`x_pos` across conveyor):
     - `x_pos < 320 - 20`: `color = (0, 180, 255)`, label `"Ayam"`
     - `abs(x_pos - 320) <= 20`: `color = (0, 255, 0)`, label `"COUNTING"`
     - `x_pos > 320 + 20`: `color = (0, 220, 0)`, label `"Ayam [COUNTED]"`

---

## 3. Error Handling & Edge Cases
1. **Missed Frames / Occlusion:** Stale tracks (`missed_frames > 0`) are not rendered on the current frame to prevent drawing ghosts.
2. **Track Eviction:** Counted tracks maintain their state until evicted by `max_allowed_missed` (capped at 3 frames after being counted in tracker logic).
3. **Empty Detections:** Zero detections render cleanly with virtual line and HUD unchanged.

---

## 4. Testing & Verification Plan

### 4.1 Unit Tests
- `services/counter/tests/test_tracking.py`:
  - Verify `TrackedObject` holds `bbox`, `class_name`, `confidence`.
  - Verify `ChickenCounter.update()` preserves and updates bounding box coordinates as tracks move.
  - Verify `track.counted` flips to `True` upon line crossing and remains `True`.
- `services/counter/tests/test_main.py`:
  - Verify `_render_window_frame()` functions correctly with tracks in both uncounted and counted states.
- `services/api/tests/test_preview_api.py`:
  - Verify `FrameGenerator.generate_frame()` returns valid JPEG payload with uncounted, crossing, and counted bounding box states.

### 4.2 Regression Testing
- Execute pytest across both service suites:
  - `pytest services/counter/tests`
  - `pytest services/api/tests`
