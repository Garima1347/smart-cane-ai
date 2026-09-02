"""
Performance optimization: without this, the main loop does
  camera.read() [blocks on I/O]  ->  YOLO inference [blocks on CPU]
sequentially, every cycle. On a Pi 5, camera I/O and inference fighting for
the same loop wastes time — camera capture can happen while the previous
frame is still being processed.

This wraps any camera object (OpenCVCamera or PiCamera2Camera from camera.py)
in a background thread that continuously reads frames and stores only the
LATEST one. The main loop just grabs whatever's freshest when it's ready for
it, instead of waiting on I/O — this alone typically recovers several FPS
on Pi 5 CPU-bound YOLO inference.
"""

import logging
import threading

logger = logging.getLogger("smart_cane")


class ThreadedCameraStream:
    def __init__(self, camera):
        """camera: an already-constructed OpenCVCamera or PiCamera2Camera (see camera.py)."""
        self._camera = camera
        self._lock = threading.Lock()
        self._latest_frame = None
        self._latest_success = False
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._frames_captured = 0

    def start(self):
        self._thread.start()
        logger.info("Threaded camera capture started")
        return self

    def _capture_loop(self):
        while not self._stop_event.is_set():
            success, frame = self._camera.read()
            with self._lock:
                self._latest_success = success
                self._latest_frame = frame
                if success:
                    self._frames_captured += 1

    def read(self):
        """Matches the OpenCVCamera/PiCamera2Camera interface — returns (success, frame)."""
        with self._lock:
            return self._latest_success, self._latest_frame

    @property
    def frames_captured(self) -> int:
        return self._frames_captured

    def release(self):
        self._stop_event.set()
        self._thread.join(timeout=1.0)
        self._camera.release()
