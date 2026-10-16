"""Tests for Detector abstractions and Mock/ONNX implementations."""

from dataclasses import FrozenInstanceError
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from services.counter.src.detection.detector import (
    Detection,
    Detector,
    MockDetector,
    ONNXDetector,
    ShackleDetector,
)


def test_cannot_instantiate_abstract_detector():
    """Verify Detector ABC cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Detector()  # type: ignore[abstract]


def test_detection_dataclass_properties():
    """Verify Detection dataclass fields, frozen immutability, and anchor_bottom_center."""
    det = Detection(
        x1=100.0,
        y1=50.0,
        x2=200.0,
        y2=150.0,
        confidence=0.92,
        class_id=0,
        class_name="chicken",
    )

    assert det.x1 == 100.0
    assert det.y1 == 50.0
    assert det.x2 == 200.0
    assert det.y2 == 150.0
    assert det.confidence == 0.92
    assert det.class_id == 0
    assert det.class_name == "chicken"

    # Bottom-center anchor point: ((x1 + x2) / 2, y2)
    assert det.anchor_bottom_center == (150.0, 150.0)

    # Immutability check
    with pytest.raises(FrozenInstanceError):
        det.confidence = 0.5  # type: ignore[misc]

    # Width and height properties
    assert det.width == 100.0
    assert det.height == 100.0


def test_mock_detector_detects_moving_targets():
    """Verify MockDetector identifies simulated chicken blob correctly."""
    detector = MockDetector(min_confidence=0.8)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Paint white blob simulating chicken
    frame[100:160, 200:250] = 220

    detections = detector.predict(frame)
    assert len(detections) >= 1
    det = detections[0]
    assert isinstance(det, Detection)
    assert det.confidence >= 0.8
    assert det.class_id == 0
    assert det.class_name == "chicken"
    assert det.x2 > det.x1
    assert det.y2 > det.y1
    assert det.x1 >= 195.0 and det.x2 <= 255.0
    assert det.y1 >= 95.0 and det.y2 <= 165.0
    # Anchor point should be at bottom-center
    anchor_x, anchor_y = det.anchor_bottom_center
    assert det.x1 <= anchor_x <= det.x2
    assert anchor_y == det.y2


def test_mock_detector_empty_or_dark_frame_returns_empty():
    """Verify MockDetector returns empty list on dark or low-intensity frames."""
    detector = MockDetector(min_confidence=0.85)

    # All black frame
    black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert detector.predict(black_frame) == []

    # Low-contrast background frame below threshold 150
    dim_frame = np.full((480, 640, 3), 100, dtype=np.uint8)
    assert detector.predict(dim_frame) == []


def test_mock_detector_filters_small_blobs():
    """Verify MockDetector filters out noise blobs smaller than minimum dimensions."""
    detector = MockDetector(min_confidence=0.85, min_width=10.0, min_height=10.0)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # 5x5 tiny bright spot (noise)
    frame[50:55, 50:55] = 255

    detections = detector.predict(frame)
    assert detections == []


def test_mock_detector_detects_multiple_blobs():
    """Verify MockDetector identifies multiple separate chicken blobs in one frame."""
    detector = MockDetector(min_confidence=0.85)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Blob 1 (left)
    frame[50:110, 100:160] = 230
    # Blob 2 (right)
    frame[250:310, 400:460] = 230

    detections = detector.predict(frame)
    assert len(detections) == 2
    # Check that both distinct regions are represented
    x_centers = [(d.x1 + d.x2) / 2.0 for d in detections]
    assert any(x < 250 for x in x_centers)
    assert any(x > 300 for x in x_centers)


def test_onnx_detector_raises_when_onnxruntime_missing():
    """Verify ONNXDetector raises descriptive RuntimeError when onnxruntime is unavailable."""
    with patch.dict(sys.modules, {"onnxruntime": None}):
        with pytest.raises(RuntimeError, match="onnxruntime"):
            ONNXDetector("models/yolo26n.onnx")


def test_onnx_detector_mocked_end_to_end_yolo26():
    """Verify ONNXDetector with mocked YOLO26 (NMS-free [N, 6]) model output."""
    mock_ort = MagicMock()
    mock_session = MagicMock()

    # Mock model input metadata
    mock_input = MagicMock()
    mock_input.name = "images"
    mock_input.shape = [1, 3, 640, 640]
    mock_session.get_inputs.return_value = [mock_input]

    # Mock model output: 2 detections in 640x640 space:
    # 1. Chicken with conf 0.9 (box [100, 100, 200, 200], class 0)
    # 2. Low-confidence detection with conf 0.2 (box [300, 300, 400, 400], class 0)
    mock_output_data = np.array(
        [
            [
                [100.0, 100.0, 200.0, 200.0, 0.90, 0.0],
                [300.0, 300.0, 400.0, 400.0, 0.20, 0.0],
            ]
        ],
        dtype=np.float32,
    )
    mock_session.run.return_value = [mock_output_data]
    mock_ort.InferenceSession.return_value = mock_session

    with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
        detector = ONNXDetector(
            model_path="models/yolo26n.onnx",
            conf_threshold=0.5,
            iou_threshold=0.45,
            class_names=["chicken"],
        )

        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = detector.predict(test_frame)

        # Only high confidence (0.90) detection should survive threshold (0.50)
        assert len(detections) == 1
        det = detections[0]
        assert det.class_id == 0
        assert det.class_name == "chicken"
        assert pytest.approx(det.confidence, 0.01) == 0.90
        # Check coordinates scaled back from 640x640 to 640x480
        # In 640x640 input, x: 100 -> 640/640 * 100 = 100
        # y: 100 -> 480/640 * 100 = 75
        assert pytest.approx(det.x1, 1.0) == 100.0
        assert pytest.approx(det.y1, 1.0) == 75.0
        assert pytest.approx(det.x2, 1.0) == 200.0
        assert pytest.approx(det.y2, 1.0) == 150.0
        assert det.anchor_bottom_center == pytest.approx((150.0, 150.0), abs=1.0)


def test_onnx_detector_mocked_raw_yolo_with_nms():
    """Verify ONNXDetector handles raw YOLO [1, 4+classes, N] outputs with NMS."""
    mock_ort = MagicMock()
    mock_session = MagicMock()

    mock_input = MagicMock()
    mock_input.name = "images"
    mock_input.shape = [1, 3, 640, 640]
    mock_session.get_inputs.return_value = [mock_input]

    # YOLO raw format: [batch, 4 + num_classes, num_anchors]
    # Here 1 class, 3 candidate boxes:
    # Box 1: [cx=150, cy=150, w=100, h=100, score=0.85] -> x1=100, y1=100, x2=200, y2=200
    # Box 2: [cx=152, cy=152, w=98, h=98, score=0.75] -> overlapping Box 1 (should be suppressed by NMS)
    # Box 3: [cx=450, cy=350, w=80, h=80, score=0.88] -> distant box
    raw_preds = np.zeros((1, 5, 3), dtype=np.float32)
    # Box 1
    raw_preds[0, :, 0] = [150.0, 150.0, 100.0, 100.0, 0.85]
    # Box 2 (overlap)
    raw_preds[0, :, 1] = [152.0, 152.0, 98.0, 98.0, 0.75]
    # Box 3
    raw_preds[0, :, 2] = [450.0, 350.0, 80.0, 80.0, 0.88]

    mock_session.run.return_value = [raw_preds]
    mock_ort.InferenceSession.return_value = mock_session

    with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
        detector = ONNXDetector(
            model_path="models/yolo11n.onnx",
            conf_threshold=0.5,
            iou_threshold=0.45,
            class_names=["chicken"],
        )

        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = detector.predict(test_frame)

        # Box 2 should have been suppressed by NMS against Box 1
        assert len(detections) == 2
        confidences = sorted([d.confidence for d in detections], reverse=True)
        assert pytest.approx(confidences[0], 0.01) == 0.88
        assert pytest.approx(confidences[1], 0.01) == 0.85


def test_mock_detector_edge_cases():
    """Verify MockDetector handles None, empty, and 2D grayscale frames cleanly."""
    detector = MockDetector()

    assert detector.predict(None) == []  # type: ignore[arg-type]
    assert detector.predict(np.array([])) == []

    # 2D grayscale frame with bright blob
    gray_frame = np.zeros((200, 200), dtype=np.uint8)
    gray_frame[50:80, 50:80] = 200
    detections = detector.predict(gray_frame)
    assert len(detections) == 1
    assert detections[0].class_name == "chicken"


def test_onnx_detector_edge_cases_and_options():
    """Verify ONNXDetector handles empty frames, custom providers, and dictionary class_names."""
    mock_ort = MagicMock()
    mock_session = MagicMock()
    mock_input = MagicMock()
    mock_input.name = "images"
    mock_input.shape = [1, 3, 320, 320]
    mock_session.get_inputs.return_value = [mock_input]
    mock_ort.InferenceSession.return_value = mock_session
    mock_ort.get_available_providers.return_value = ["CPUExecutionProvider"]

    with patch.dict(sys.modules, {"onnxruntime": mock_ort}):
        detector = ONNXDetector(
            model_path="models/custom.onnx",
            conf_threshold=0.6,
            providers=["CPUExecutionProvider"],
            class_names={0: "broiler", 1: "layer"},
        )

        # Empty and None frame handling
        assert detector.predict(None) == []  # type: ignore[arg-type]
        assert detector.predict(np.array([])) == []

        # Empty session output
        mock_session.run.return_value = []
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        assert detector.predict(frame) == []


def test_shackle_detector_empty_and_blank():
    """Verify ShackleDetector handles None, empty, and flat zero-gradient frames."""
    detector = ShackleDetector()
    assert detector.predict(None) == []  # type: ignore[arg-type]
    assert detector.predict(np.array([])) == []

    flat_frame = np.full((1080, 1920, 3), 128, dtype=np.uint8)
    assert detector.predict(flat_frame) == []


def test_shackle_detector_detects_spaced_shackles():
    """Verify ShackleDetector locates vertical bars and frames suspended objects."""
    detector = ShackleDetector(
        shackle_y_ratio=(0.20, 0.50),
        min_spacing=50.0,
        chicken_width=80.0,
        chicken_height=300.0,
        chicken_y_top=250.0,
        occupancy_check=False,
    )
    frame = np.zeros((600, 800, 3), dtype=np.uint8)
    # Draw three distinct vertical shackle bars in the shackle band y in [120, 300]
    frame[150:280, 195:205] = 255
    frame[150:280, 395:405] = 255
    frame[150:280, 595:605] = 255

    detections = detector.predict(frame)
    assert len(detections) == 3
    for det in detections:
        assert isinstance(det, Detection)
        assert det.class_name == "chicken"
        assert det.confidence == 0.90
        assert det.y1 == 250.0
        assert det.y2 == 550.0

    centers = [(d.x1 + d.x2) / 2.0 for d in detections]
    assert pytest.approx(centers[0], abs=15) == 200.0
    assert pytest.approx(centers[1], abs=15) == 400.0
    assert pytest.approx(centers[2], abs=15) == 600.0


def test_mock_detector_area_and_morph_filters():
    """Verify MockDetector respects min_area, max_area, and morph_open."""
    detector = MockDetector(
        min_confidence=0.85,
        min_width=5.0,
        min_height=5.0,
        min_area=100.0,
        max_area=5000.0,
        morph_open=True,
    )
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Small speckle (area 16) - below min_area
    frame[50:54, 50:54] = 255
    # Medium blob (area 900) - valid
    frame[100:130, 100:130] = 255
    # Huge background blob (area 10,000) - exceeds max_area
    frame[200:300, 200:300] = 255

    detections = detector.predict(frame)
    assert len(detections) == 1
    det = detections[0]
    assert 95.0 <= det.x1 <= 105.0
    assert 125.0 <= det.x2 <= 135.0


def test_shackle_detector_rejects_empty_shackle():
    """Verify ShackleDetector rejects empty shackles where no chicken carcass is present."""
    detector = ShackleDetector(
        shackle_y_ratio=(0.20, 0.50),
        min_spacing=50.0,
        chicken_width=80.0,
        chicken_height=300.0,
        chicken_y_top=250.0,
        occupancy_check=True,
    )
    frame = np.zeros((600, 800, 3), dtype=np.uint8)
    # Shackle 1 at cx=200 has a chicken carcass below it
    frame[150:280, 195:205] = 255
    frame[370:440, 197:203] = 220  # carcass presence in [0.62*h, 0.74*h]

    # Shackle 2 at cx=400 is EMPTY (only the metal bar, zero carcass below)
    frame[150:280, 395:405] = 255

    # Shackle 3 at cx=600 has a chicken carcass below it
    frame[150:280, 595:605] = 255
    frame[370:440, 597:603] = 220

    detections = detector.predict(frame)
    # Only the 2 occupied shackles should be detected; empty shackle at cx=400 must be rejected
    assert len(detections) == 2
    centers = [(d.x1 + d.x2) / 2.0 for d in detections]
    assert pytest.approx(centers[0], abs=15) == 200.0
    assert pytest.approx(centers[1], abs=15) == 600.0


def test_shackle_detector_occupancy_check_disabled_detects_all():
    """Verify ShackleDetector with occupancy_check=False detects all shackle brackets."""
    detector = ShackleDetector(
        shackle_y_ratio=(0.20, 0.50),
        min_spacing=50.0,
        chicken_width=80.0,
        chicken_height=300.0,
        chicken_y_top=250.0,
        occupancy_check=False,
    )
    frame = np.zeros((600, 800, 3), dtype=np.uint8)
    frame[150:280, 195:205] = 255
    frame[150:280, 395:405] = 255  # Empty shackle

    detections = detector.predict(frame)
    assert len(detections) == 2


def test_shackle_detector_video_frame_rejects_empty_shackle():
    """Verify ShackleDetector on Rekaman_2.MOV frame 3160 suppresses empty shackle at cx ~ 1322."""
    import os
    import cv2

    video_path = "samples/Rekaman_2.MOV"
    if not os.path.exists(video_path):
        pytest.skip(f"Video file {video_path} not found")

    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 3160)
    ret, frame = cap.read()
    cap.release()
    assert ret and frame is not None

    detector = ShackleDetector(occupancy_check=True)
    detections = detector.predict(frame)

    # In frame 3160, the empty shackle bracket is at cx ~ 1322
    # Verify no detection has center in range [1300, 1345]
    empty_shackle_dets = [
        d for d in detections if 1300.0 <= (d.x1 + d.x2) / 2.0 <= 1345.0
    ]
    assert len(empty_shackle_dets) == 0

    # Ensure occupied chickens on both sides are still detected
    occupied_left = [
        d for d in detections if 1200.0 <= (d.x1 + d.x2) / 2.0 <= 1245.0
    ]
    occupied_right = [
        d for d in detections if 1420.0 <= (d.x1 + d.x2) / 2.0 <= 1460.0
    ]
    assert len(occupied_left) == 1
    assert len(occupied_right) == 1


def test_shackle_detector_noise_rejection_and_bracket_clustering():
    """Verify ShackleDetector groups paired bracket bars accurately without cascading into noise."""
    detector = ShackleDetector(
        shackle_y_ratio=(0.20, 0.50),
        min_spacing=55.0,
        chicken_width=80.0,
        chicken_height=300.0,
        chicken_y_top=250.0,
        occupancy_check=False,
    )
    frame = np.zeros((600, 800, 3), dtype=np.uint8)

    # Shackle bracket 1 at cx=300: two vertical bars at 292 and 308 (intensity 255)
    frame[150:280, 290:294] = 255
    frame[150:280, 306:310] = 255

    # Faint noise reflection nearby at x=345 (intensity 50, below 40% of max energy)
    frame[150:280, 344:346] = 50

    # Shackle bracket 2 at cx=500: two vertical bars at 492 and 508
    frame[150:280, 490:494] = 255
    frame[150:280, 506:510] = 255

    detections = detector.predict(frame)
    assert len(detections) == 2
    centers = [(d.x1 + d.x2) / 2.0 for d in detections]
    assert pytest.approx(centers[0], abs=5) == 300.0
    assert pytest.approx(centers[1], abs=5) == 500.0



