"""Detector abstractions and concrete detector implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence
import cv2
import numpy as np

__all__ = ["Detection", "Detector", "MockDetector", "ONNXDetector"]


@dataclass(frozen=True)
class Detection:
    """Bounding box detection with class information and anchor point."""

    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int
    class_name: str

    @property
    def anchor_bottom_center(self) -> tuple[float, float]:
        """Anchor point used for virtual line crossing (x_mid, y2)."""
        return ((self.x1 + self.x2) / 2.0, self.y2)

    @property
    def width(self) -> float:
        """Width of bounding box."""
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        """Height of bounding box."""
        return max(0.0, self.y2 - self.y1)


class Detector(ABC):
    """Abstract base class for all object detectors."""

    @abstractmethod
    def predict(self, frame: np.ndarray) -> list[Detection]:
        """Run inference on the given BGR frame and return a list of detections.

        Args:
            frame: Numpy array containing BGR image frame (H, W, C).

        Returns:
            List of Detection objects detected in the frame.
        """
        pass


class MockDetector(Detector):
    """Threshold-based procedural detector for testing without deep learning models."""

    def __init__(
        self,
        min_confidence: float = 0.85,
        min_width: float = 10.0,
        min_height: float = 10.0,
        intensity_threshold: int = 150,
        class_name: str = "chicken",
        class_id: int = 0,
    ) -> None:
        self.min_confidence = min_confidence
        self.min_width = min_width
        self.min_height = min_height
        self.intensity_threshold = intensity_threshold
        self.class_name = class_name
        self.class_id = class_id

    def predict(self, frame: np.ndarray) -> list[Detection]:
        """Detect bright contour regions above the intensity threshold."""
        detections: list[Detection] = []
        if frame is None or frame.size == 0:
            return detections

        if frame.ndim == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        _, thresh = cv2.threshold(
            gray, self.intensity_threshold, 255, cv2.THRESH_BINARY
        )
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if float(w) > self.min_width and float(h) > self.min_height:
                detections.append(
                    Detection(
                        x1=float(x),
                        y1=float(y),
                        x2=float(x + w),
                        y2=float(y + h),
                        confidence=self.min_confidence,
                        class_id=self.class_id,
                        class_name=self.class_name,
                    )
                )
        return detections


class ONNXDetector(Detector):
    """ONNX Runtime detector supporting YOLO26 (NMS-free) and standard YOLO models."""

    def __init__(
        self,
        model_path: str,
        conf_threshold: float = 0.5,
        iou_threshold: float = 0.45,
        providers: list[str] | None = None,
        class_names: Sequence[str] | dict[int, str] | None = None,
    ) -> None:
        self.model_path = str(model_path)
        self.conf_threshold = float(conf_threshold)
        self.iou_threshold = float(iou_threshold)

        if class_names is None:
            self.class_names: dict[int, str] = {0: "chicken"}
        elif isinstance(class_names, dict):
            self.class_names = class_names
        else:
            self.class_names = {idx: name for idx, name in enumerate(class_names)}

        try:
            import onnxruntime as ort

            if ort is None:
                raise ImportError("onnxruntime is None")
        except Exception as exc:
            raise RuntimeError(
                f"onnxruntime is not installed or unavailable: {exc}. "
                "Please install onnxruntime or onnxruntime-gpu to use ONNXDetector."
            ) from exc

        if providers is None:
            available = (
                ort.get_available_providers()
                if hasattr(ort, "get_available_providers")
                else []
            )
            preferred = [
                "CUDAExecutionProvider",
                "TensorrtExecutionProvider",
                "CoreMLExecutionProvider",
                "OpenVINOExecutionProvider",
                "CPUExecutionProvider",
            ]
            providers = [p for p in preferred if p in available]
            if not providers:
                providers = ["CPUExecutionProvider"]

        self.session = ort.InferenceSession(self.model_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name

        # Parse input shape from model metadata
        input_shape = self.session.get_inputs()[0].shape
        if (
            len(input_shape) >= 4
            and isinstance(input_shape[2], int)
            and isinstance(input_shape[3], int)
        ):
            self.input_height = input_shape[2]
            self.input_width = input_shape[3]
        else:
            self.input_height = 640
            self.input_width = 640

    def predict(self, frame: np.ndarray) -> list[Detection]:
        """Preprocess frame, run ONNX inference, and parse detection boxes."""
        if frame is None or frame.size == 0:
            return []

        orig_h, orig_w = frame.shape[:2]

        # Preprocess: resize, BGR -> RGB, HWC -> CHW, normalize to [0, 1]
        resized = cv2.resize(frame, (self.input_width, self.input_height))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        tensor = (rgb.transpose(2, 0, 1).astype(np.float32) / 255.0)[np.newaxis, ...]

        outputs = self.session.run(None, {self.input_name: tensor})
        if not outputs:
            return []

        raw = outputs[0]
        if raw.ndim == 3 and raw.shape[0] == 1:
            raw = raw[0]

        scale_x = orig_w / float(self.input_width)
        scale_y = orig_h / float(self.input_height)

        # Check output structure:
        # Case 1: YOLO26 / end-to-end NMS-free format: [N, 6] -> (x1, y1, x2, y2, conf, cls_id)
        if raw.ndim == 2 and (
            raw.shape[1] == 6 or (raw.shape[0] == 6 and raw.shape[1] > 6)
        ):
            if raw.shape[0] == 6 and raw.shape[1] > 6:
                raw = raw.T

            detections: list[Detection] = []
            for row in raw:
                x1, y1, x2, y2, conf, cls_id = row
                if conf < self.conf_threshold:
                    continue

                cid = int(cls_id)
                cname = self.class_names.get(cid, str(cid))
                detections.append(
                    Detection(
                        x1=float(x1 * scale_x),
                        y1=float(y1 * scale_y),
                        x2=float(x2 * scale_x),
                        y2=float(y2 * scale_y),
                        confidence=float(conf),
                        class_id=cid,
                        class_name=cname,
                    )
                )
            return detections

        # Case 2: Raw YOLO format: [4 + num_classes, N] or [N, 4 + num_classes]
        if raw.ndim == 2:
            expected_feat = 4 + len(self.class_names)
            if raw.shape[0] == expected_feat and raw.shape[1] != expected_feat:
                raw = raw.T
            elif raw.shape[1] < 5 and raw.shape[0] >= 5:
                raw = raw.T
            elif raw.shape[0] < raw.shape[1] and raw.shape[0] <= 100 < raw.shape[1]:
                raw = raw.T

            candidate_detections: list[Detection] = []
            nms_boxes: list[list[int]] = []
            nms_scores: list[float] = []

            for row in raw:
                if len(row) < 5:
                    continue
                cx, cy, w, h = row[:4]
                class_scores = row[4:]
                if len(class_scores) == 0:
                    continue

                best_cls = int(np.argmax(class_scores))
                best_conf = float(class_scores[best_cls])
                if best_conf < self.conf_threshold:
                    continue

                real_x1 = max(0.0, float((cx - w / 2.0) * scale_x))
                real_y1 = max(0.0, float((cy - h / 2.0) * scale_y))
                real_x2 = min(float(orig_w), float((cx + w / 2.0) * scale_x))
                real_y2 = min(float(orig_h), float((cy + h / 2.0) * scale_y))

                candidate_detections.append(
                    Detection(
                        x1=real_x1,
                        y1=real_y1,
                        x2=real_x2,
                        y2=real_y2,
                        confidence=best_conf,
                        class_id=best_cls,
                        class_name=self.class_names.get(best_cls, str(best_cls)),
                    )
                )
                nms_boxes.append(
                    [
                        int(real_x1),
                        int(real_y1),
                        int(max(0.0, real_x2 - real_x1)),
                        int(max(0.0, real_y2 - real_y1)),
                    ]
                )
                nms_scores.append(best_conf)

            if not nms_boxes:
                return []

            indices = cv2.dnn.NMSBoxes(
                nms_boxes,
                nms_scores,
                self.conf_threshold,
                self.iou_threshold,
            )

            results: list[Detection] = []
            if len(indices) > 0:
                for idx in np.array(indices).flatten():
                    results.append(candidate_detections[idx])
            return results

        return []
