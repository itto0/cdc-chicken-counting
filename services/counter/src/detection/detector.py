"""Detector abstractions and concrete detector implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence
import cv2
import numpy as np

__all__ = ["Detection", "Detector", "MockDetector", "ONNXDetector", "ShackleDetector"]


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
        min_area: float = 0.0,
        max_area: float | None = None,
        intensity_threshold: int = 150,
        class_name: str = "chicken",
        class_id: int = 0,
        apply_blur: bool = False,
        morph_open: bool = False,
        roi: tuple[int, int, int, int] | None = None,
    ) -> None:
        self.min_confidence = min_confidence
        self.min_width = min_width
        self.min_height = min_height
        self.min_area = min_area
        self.max_area = max_area
        self.intensity_threshold = intensity_threshold
        self.class_name = class_name
        self.class_id = class_id
        self.apply_blur = apply_blur
        self.morph_open = morph_open
        self.roi = roi

    def predict(self, frame: np.ndarray) -> list[Detection]:
        """Detect bright contour regions above the intensity threshold."""
        detections: list[Detection] = []
        if frame is None or frame.size == 0:
            return detections

        x_offset, y_offset = 0, 0
        working_frame = frame
        if self.roi is not None:
            ymin, ymax, xmin, xmax = self.roi
            working_frame = working_frame[ymin:ymax, xmin:xmax]
            x_offset, y_offset = xmin, ymin
            if working_frame.size == 0:
                return detections

        if working_frame.ndim == 3:
            gray = cv2.cvtColor(working_frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = working_frame

        if self.apply_blur:
            gray = cv2.GaussianBlur(gray, (7, 7), 0)

        _, thresh = cv2.threshold(
            gray, self.intensity_threshold, 255, cv2.THRESH_BINARY
        )

        if self.morph_open:
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        for cnt in contours:
            area = float(cv2.contourArea(cnt))
            if self.min_area > 0 and area < self.min_area:
                continue
            if self.max_area is not None and area > self.max_area:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            if float(w) > self.min_width and float(h) > self.min_height:
                detections.append(
                    Detection(
                        x1=float(x + x_offset),
                        y1=float(y + y_offset),
                        x2=float(x + w + x_offset),
                        y2=float(y + h + y_offset),
                        confidence=self.min_confidence,
                        class_id=self.class_id,
                        class_name=self.class_name,
                    )
                )
        return detections


class ShackleDetector(Detector):
    """Specialized detector for industrial poultry on overhead shackle conveyor lines.

    Analyzes vertical steel shackle brackets to locate regularly spaced shackle centers,
    then frames each suspended chicken carcass with high spatial stability.
    """

    def __init__(
        self,
        min_confidence: float = 0.90,
        shackle_y_ratio: tuple[float, float] = (0.24, 0.48),
        min_spacing: float = 55.0,
        chicken_width: float = 115.0,
        chicken_height: float = 580.0,
        chicken_y_top: float | None = 260.0,
        chicken_y_top_ratio: float = 0.25,
        class_name: str = "chicken",
        class_id: int = 0,
        occupancy_check: bool = True,
        carcass_y_ratio: tuple[float, float] = (0.62, 0.76),
        occupancy_threshold: float = 4.5,
        min_peak_energy: float = 12.0,
        max_bar_spacing: float = 25.0,
    ) -> None:
        self.min_confidence = min_confidence
        self.shackle_y_ratio = shackle_y_ratio
        self.min_spacing = min_spacing
        self.chicken_width = chicken_width
        self.chicken_height = chicken_height
        self.chicken_y_top = chicken_y_top
        self.chicken_y_top_ratio = chicken_y_top_ratio
        self.class_name = class_name
        self.class_id = class_id
        self.occupancy_check = occupancy_check
        self.carcass_y_ratio = carcass_y_ratio
        self.occupancy_threshold = occupancy_threshold
        self.min_peak_energy = min_peak_energy
        self.max_bar_spacing = max_bar_spacing

    def predict(self, frame: np.ndarray) -> list[Detection]:
        """Detect individual chickens on the shackle line with regular spacing."""
        detections: list[Detection] = []
        if frame is None or frame.size == 0:
            return detections

        h, w = frame.shape[:2]
        y1_shackle = int(max(0.0, min(1.0, self.shackle_y_ratio[0])) * h)
        y2_shackle = int(max(0.0, min(1.0, self.shackle_y_ratio[1])) * h)
        if y2_shackle <= y1_shackle:
            return detections

        shackle_roi = frame[y1_shackle:y2_shackle, :]
        if shackle_roi.ndim == 3:
            gray = cv2.cvtColor(shackle_roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = shackle_roi

        sobelx = np.abs(cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)).astype(np.uint8)
        col_energy = cv2.GaussianBlur(
            sobelx.mean(axis=0).reshape(1, -1), (25, 1), 0
        ).flatten()

        max_energy = float(col_energy.max()) if len(col_energy) > 0 else 0.0
        if max_energy < 10.0:
            return detections

        threshold = max(self.min_peak_energy, float(max_energy * 0.40))
        peaks: list[tuple[int, float]] = []
        i = 1
        n = len(col_energy)
        while i < n - 1:
            if col_energy[i] >= threshold and col_energy[i] > col_energy[i - 1]:
                start = i
                while i < n - 1 and col_energy[i] == col_energy[i + 1]:
                    i += 1
                if i < n - 1 and col_energy[i] > col_energy[i + 1]:
                    peak_pos = (start + i) // 2
                    peaks.append((peak_pos, float(col_energy[start])))
            i += 1

        # Cluster paired bracket bars (separated by <= max_bar_spacing)
        clusters: list[list[tuple[int, float]]] = []
        for p, val in peaks:
            if not clusters:
                clusters.append([(p, val)])
            elif (p - clusters[-1][-1][0]) <= self.max_bar_spacing:
                clusters[-1].append((p, val))
            else:
                clusters.append([(p, val)])

        cluster_info: list[tuple[int, float]] = []
        for c in clusters:
            cx = int(np.mean([pt[0] for pt in c]))
            max_val = max(pt[1] for pt in c)
            cluster_info.append((cx, max_val))

        # Filter clusters closer than min_spacing (retain stronger bracket candidate)
        filtered_centers: list[tuple[int, float]] = []
        for cx, val in cluster_info:
            if not filtered_centers:
                filtered_centers.append((cx, val))
            elif (cx - filtered_centers[-1][0]) < self.min_spacing:
                if val > filtered_centers[-1][1]:
                    filtered_centers[-1] = (cx, val)
            else:
                filtered_centers.append((cx, val))

        centers = [c[0] for c in filtered_centers]

        y_top = (
            self.chicken_y_top
            if self.chicken_y_top is not None
            else float(h * self.chicken_y_top_ratio)
        )
        box_w = float(self.chicken_width)
        box_h = float(self.chicken_height)

        full_gray = None
        y1_carcass = 0
        y2_carcass = 0
        if self.occupancy_check:
            full_gray = (
                cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if frame.ndim == 3
                else frame
            )
            y1_carcass = int(max(0.0, min(1.0, self.carcass_y_ratio[0])) * h)
            y2_carcass = int(max(0.0, min(1.0, self.carcass_y_ratio[1])) * h)

        for cx in centers:
            if self.occupancy_check and full_gray is not None and y2_carcass > y1_carcass:
                pw = max(6, int(0.006 * w))
                px1 = max(0, cx - pw)
                px2 = min(w, cx + pw)
                patch = full_gray[y1_carcass:y2_carcass, px1:px2]
                if patch.size == 0:
                    continue
                sx = float(np.abs(cv2.Sobel(patch, cv2.CV_16S, 1, 0)).mean())
                if sx < self.occupancy_threshold:
                    continue

            x1 = max(0.0, float(cx - box_w / 2.0))
            x2 = min(float(w), float(cx + box_w / 2.0))
            y1 = max(0.0, float(y_top))
            y2 = min(float(h), float(y_top + box_h))
            detections.append(
                Detection(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
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
