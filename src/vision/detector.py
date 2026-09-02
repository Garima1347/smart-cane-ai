
"""
Multi-model YOLO detector for Smart Cane.

Models:
    - YOLO11n       -> general objects
    - best_door.pt  -> door
    - best_pothole.pt -> pothole + road cracks

Each detection contains:
    - label
    - confidence
    - direction: left / center / right
    - rough_distance: near / medium / far
    - bbox: (x1, y1, x2, y2)
"""
import logging
from ultralytics import YOLO

logger = logging.getLogger("smart_cane")


class ObjectDetector:
    def __init__(
        self,
        models=None,
        confidence_threshold: float = 0.45,
        inference_size: int = 320,
    ):
        """
        Load all YOLO models.

        models should be a dictionary like:

        {
            "general": "model/yolo11n.pt",
            "door": "model/best_door.pt",
            "road_hazard": "model/best_pothole.pt",
        }
        """

        if models is None:
            models = {
                "general": "model/yolo11n.pt",
                "door": "model/best_door.pt",
                "road_hazard": "model/best_pothole.pt",
            }

        self.models = {}

        for model_name, model_path in models.items():
            logger.info(f"Loading {model_name} model: {model_path}")
            self.models[model_name] = YOLO(model_path)

        self.confidence_threshold = confidence_threshold
        self.inference_size = inference_size

        logger.info("All YOLO models loaded successfully.")

    def detect(self, frame):
        """
        Run all YOLO models on a single BGR frame.

        Returns:
            list of detection dictionaries.
        """

        h, w = frame.shape[:2]
        detections = []

        for model_name, model in self.models.items():

            results = model.predict(
                source=frame,
                imgsz=self.inference_size,
                conf=self.confidence_threshold,
                verbose=False,
            )

            if not results:
                continue

            result = results[0]

            for box in result.boxes:

                x1, y1, x2, y2 = box.xyxy[0].tolist()

                conf = float(box.conf[0])
                cls_id = int(box.cls[0])

                label = model.names[cls_id]

                center_x = (x1 + x2) / 2

                direction = self._get_direction(
                    center_x,
                    w
                )

                bbox_area_ratio = (
                    (x2 - x1) * (y2 - y1)
                ) / (w * h)

                rough_distance = self._get_rough_distance(
                    bbox_area_ratio
                )

                detections.append({
                    "label": label,
                    "confidence": conf,
                    "direction": direction,
                    "rough_distance": rough_distance,
                    "bbox": (
                        int(x1),
                        int(y1),
                        int(x2),
                        int(y2),
                    ),
                    "model": model_name,
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
    def _get_rough_distance(
        bbox_area_ratio: float
    ) -> str:

        # Larger bounding box = object is probably closer.

        if bbox_area_ratio > 0.25:
            return "near"

        elif bbox_area_ratio > 0.08:
            return "medium"

        else:
            return "far"
