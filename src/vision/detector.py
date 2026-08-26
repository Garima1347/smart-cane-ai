"""
YOLOv8 wrapper. Runs detection on a frame and returns a clean list of
detections, each annotated with:
  - label (e.g. "person", "car", "chair")
  - confidence
  - direction: "left" / "center" / "right" (based on bbox position in frame)
  - rough_distance: "near" / "medium" / "far" (based on bbox size — a proxy,
    NOT a precise measurement; precise close-range distance comes from the
    ultrasonic sensor instead)
  - bbox: (x1, y1, x2, y2)

Model weights (yolov8n.pt) auto-download from Ultralytics on first run and
are cached in models/.
"""

import logging
from ultralytics import YOLO

logger = logging.getLogger("smart_cane")


class ObjectDetector:
    def __init__(self, model_path: str = "yolov8n.pt", confidence_threshold: float = 0.45,
                 inference_size: int = 320):
        logger.info(f"Loading YOLO model: {model_path} (this may download weights on first run)")
        self.model = YOLO(model_path)
        self.confidence_threshold = confidence_threshold
        self.inference_size = inference_size

    def detect(self, frame):
        """
        Run detection on a single BGR frame (as returned by OpenCV).
        Returns a list of detection dicts.
        """
        h, w = frame.shape[:2]

        results = self.model.predict(
            source=frame,
            imgsz=self.inference_size,
            conf=self.confidence_threshold,
            verbose=False,
        )

        detections = []
        if not results:
            return detections

        result = results[0]
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            label = self.model.names[cls_id]

            center_x = (x1 + x2) / 2
            direction = self._get_direction(center_x, w)

            bbox_area_ratio = ((x2 - x1) * (y2 - y1)) / (w * h)
            rough_distance = self._get_rough_distance(bbox_area_ratio)

            detections.append({
                "label": label,
                "confidence": conf,
                "direction": direction,
                "rough_distance": rough_distance,
                "bbox": (int(x1), int(y1), int(x2), int(y2)),
            })

        return detections

    @staticmethod
    def _get_direction(center_x: float, frame_width: int) -> str:
        third = frame_width / 3
        if center_x < third:
            return "left"
        elif center_x < 2 * third:
            return "center"
        else:
            return "right"

    @staticmethod
    def _get_rough_distance(bbox_area_ratio: float) -> str:
        # Larger bbox relative to frame => object is closer.
        # These thresholds are tuned loosely for a chest/hand-height camera
        # at walking distance — adjust after real-world testing.
        if bbox_area_ratio > 0.25:
            return "near"
        elif bbox_area_ratio > 0.08:
            return "medium"
        else:
            return "far"
