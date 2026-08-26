"""
Cross-platform camera capture.

- On Mac: always uses OpenCV VideoCapture against the built-in/USB webcam.
- On Raspberry Pi: tries Picamera2 (official Pi Camera Module) first for best
  performance/quality; if not available or no camera module is attached,
  falls back to OpenCV VideoCapture (works with any USB webcam).

Both backends expose the same simple interface: `read()` -> (success, frame)
and `release()`, so the rest of the code never needs to know which one is
active.
"""

import cv2
import logging
from src.utils.platform_utils import IS_PI, has_picamera2

logger = logging.getLogger("smart_cane")


class OpenCVCamera:
    def __init__(self, index: int, width: int, height: int):
        self.cap = cv2.VideoCapture(index)
        if not self.cap.isOpened():
            raise RuntimeError(
                f"Could not open camera at index {index}. "
                f"Check that no other app is using the webcam, and try a different index."
            )
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        logger.info(f"OpenCV camera opened (index={index}, {width}x{height})")

    def read(self):
        return self.cap.read()

    def release(self):
        self.cap.release()


class PiCamera2Camera:
    """Wraps Picamera2 to look like an OpenCV VideoCapture (read/release)."""

    def __init__(self, width: int, height: int):
        from picamera2 import Picamera2
        self.picam2 = Picamera2()
        config = self.picam2.create_preview_configuration(
            main={"format": "RGB888", "size": (width, height)}
        )
        self.picam2.configure(config)
        self.picam2.start()
        logger.info(f"Pi Camera Module opened via Picamera2 ({width}x{height})")

    def read(self):
        frame = self.picam2.capture_array()
        return True, frame

    def release(self):
        self.picam2.stop()


def create_camera(index: int, width: int, height: int, prefer_picamera: bool = True):
    """
    Factory that returns the best available camera backend for the current
    platform. Always returns an object with .read() and .release().
    """
    if IS_PI and prefer_picamera and has_picamera2():
        try:
            return PiCamera2Camera(width, height)
        except Exception as e:
            logger.warning(f"Picamera2 init failed ({e}), falling back to OpenCV/USB camera.")

    return OpenCVCamera(index, width, height)
