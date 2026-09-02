#!/usr/bin/env python3
"""
Trains a custom YOLOv8n model on road-hazard classes (pothole, etc.).

Run this on your laptop/desktop (NOT the Raspberry Pi — training needs far
more compute than the Pi has; you train on a normal PC/laptop, or free-tier
Google Colab GPU, then copy the resulting .pt file to the Pi for inference
only).

Usage:
    python train.py                          # default settings, good starting point
    python train.py --epochs 100 --imgsz 640
    python train.py --resume                 # continue an interrupted run

After training, the best weights land in:
    runs/detect/train/weights/best.pt

Copy that file to your Pi's smart_cane/models/ folder and point
config.yaml's vision.hazard_model at it (see integration notes at the
bottom of this file).
"""

import argparse
from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser(description="Train custom road-hazard YOLO model")
    parser.add_argument("--data", default="dataset.yaml", help="Path to dataset yaml")
    parser.add_argument("--base-model", default="yolov8n.pt",
                         help="Starting weights — yolov8n.pt (fast, recommended for Pi) or yolov8s.pt (more accurate, slower)")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--imgsz", type=int, default=640, help="Training image size")
    parser.add_argument("--batch", type=int, default=16, help="Reduce if you run out of GPU memory")
    parser.add_argument("--patience", type=int, default=15, help="Stop early if no improvement for N epochs")
    parser.add_argument("--resume", action="store_true", help="Resume the last interrupted training run")
    args = parser.parse_args()

    if args.resume:
        # Ultralytics tracks the last run automatically.
        model = YOLO("runs/detect/train/weights/last.pt")
        model.train(resume=True)
        return

    # Start from COCO-pretrained weights (transfer learning) rather than
    # training from scratch — this matters a lot with a small dataset
    # (hundreds-to-low-thousands of images). The model already knows general
    # edges/textures/shapes from COCO; we're just teaching it the new classes.
    model = YOLO(args.base_model)

    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        patience=args.patience,
        # Augmentation tuned for road-surface imagery — potholes/hazards
        # need to be recognized at different angles/lighting, but flipping
        # top-to-bottom would create unrealistic "upside-down road" images,
        # so we disable vertical flip specifically.
        flipud=0.0,
        fliplr=0.5,
        hsv_h=0.015,
        hsv_s=0.5,   # more saturation jitter helps with varied road-surface colors
        hsv_v=0.4,   # more brightness jitter helps with sun/shadow variation
        degrees=5.0,  # slight rotation only — cane camera stays roughly upright
        translate=0.1,
        scale=0.3,
        mosaic=1.0,
        name="road_hazard_v1",
    )

    # Run validation on the held-out val set and print metrics.
    metrics = model.val()
    print("\n=== Validation results ===")
    print(f"mAP50: {metrics.box.map50:.3f}")
    print(f"mAP50-95: {metrics.box.map:.3f}")
    print("\nIf mAP50 is below ~0.5, you likely need more/better-labeled training data")
    print("before this model is reliable enough to deploy — see DATA_GUIDE.md.")


if __name__ == "__main__":
    main()

# ============================================================================
# INTEGRATION NOTES — how this plugs into the existing smart_cane codebase
# ============================================================================
#
# The existing src/vision/detector.py wraps ONE YOLO model. To run both the
# general COCO model AND this custom hazard model per frame, the cleanest
# approach is a second ObjectDetector instance:
#
#   coco_detector = ObjectDetector(model_path="yolov8n.pt", ...)
#   hazard_detector = ObjectDetector(model_path="models/road_hazard_v1.pt", ...)
#
#   detections = coco_detector.detect(frame) + hazard_detector.detect(frame)
#
# Both run on the same frame; results merge into one list before going into
# obstacle_logic.py's build_alerts(). Since both are YOLOv8n, running two
# passes roughly doubles inference time per frame — budget for this in your
# frame_skip / threaded_capture settings in config.yaml once you're testing
# on the actual Pi 5 hardware.
