"""Capture pipeline abstractions and concrete video sources."""

from abc import ABC, abstractmethod
import cv2
import numpy as np

__all__ = ["VideoSource", "SyntheticVideoSource", "FileVideoSource"]


class VideoSource(ABC):
    """Abstract base class for all video sources."""

    @abstractmethod
    def start(self) -> None:
        """Initialize and open the video stream or file."""
        pass

    @abstractmethod
    def read(self) -> tuple[bool, np.ndarray | None]:
        """Read the next frame.

        Returns:
            (success, frame_bgr) where frame_bgr is a numpy array in BGR format
            if success is True, or (False, None) if frame read fails or EOF.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Release video resources and stop acquisition."""
        pass

    def __enter__(self) -> "VideoSource":
        """Context manager entry - starts source."""
        self.start()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Context manager exit - stops source."""
        self.stop()


class SyntheticVideoSource(VideoSource):
    """Generates procedural frames with simulated chicken movement for testing/dev."""

    def __init__(self, width: int = 640, height: int = 480, fps: int = 30) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_idx = 0
        self.is_running = False

    def start(self) -> None:
        """Start generating synthetic video frames."""
        self.is_running = True
        self.frame_idx = 0

    def read(self) -> tuple[bool, np.ndarray | None]:
        """Read the next synthetic frame."""
        if not self.is_running:
            return False, None

        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        # Background conveyor tone
        frame[:] = (40, 40, 40)

        # Draw a moving white block representing a chicken shackle
        y_pos = (self.frame_idx * 5) % (self.height + 60) - 30
        x_pos = self.width // 2
        y1 = max(0, y_pos - 30)
        y2 = min(self.height, y_pos + 30)
        x1 = max(0, x_pos - 25)
        x2 = min(self.width, x_pos + 25)
        if y2 > y1 and x2 > x1:
            frame[y1:y2, x1:x2] = (220, 220, 220)

        self.frame_idx += 1
        return True, frame

    def stop(self) -> None:
        """Stop generating synthetic video frames."""
        self.is_running = False


class FileVideoSource(VideoSource):
    """OpenCV VideoCapture based wrapper for MP4/AVI replay with optional looping."""

    def __init__(self, file_path: str, loop: bool = False) -> None:
        self.file_path = str(file_path)
        self.loop = loop
        self.cap: cv2.VideoCapture | None = None
        self.is_running = False

    def start(self) -> None:
        """Open the video file for capture."""
        self.cap = cv2.VideoCapture(self.file_path)
        if not self.cap.isOpened():
            self.is_running = False
            return
        self.is_running = True

    def read(self) -> tuple[bool, np.ndarray | None]:
        """Read the next frame from the video file."""
        if not self.is_running or self.cap is None or not self.cap.isOpened():
            return False, None

        ret, frame = self.cap.read()
        if not ret:
            if self.loop:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                if not ret:
                    return False, None
                return True, frame
            return False, None

        return True, frame

    def stop(self) -> None:
        """Release the video file resource."""
        self.is_running = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None
