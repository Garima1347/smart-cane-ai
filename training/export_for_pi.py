#!/usr/bin/env python3
"""
Exports a trained YOLO model (.pt) to NCNN format, which runs noticeably
faster than raw PyTorch on Raspberry Pi 5's ARM CPU — typically a real
frame-rate improvement for no accuracy cost, since it's the same trained
weights, just a faster inference engine.

Run this on your laptop after training finishes, then copy the exported
folder to the Pi.

Usage:
    python export_for_pi.py --weights runs/detect/train/road_hazard_v1/weights/best.pt
"""

import argparse
from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser(description="Export a trained YOLO model for Pi 5 inference")
    parser.add_argument("--weights", required=True, help="Path to trained best.pt")
    parser.add_argument("--imgsz", type=int, default=320,
                         help="Inference size — should match config.yaml's vision.inference_size")
    args = parser.parse_args()

    model = YOLO(args.weights)

    # NCNN: best speed on Pi 5's ARM CPU, no accuracy loss (not quantized).
    model.export(format="ncnn", imgsz=args.imgsz)
    print(f"\nExported NCNN model next to {args.weights}")
    print("Copy the resulting '..._ncnn_model' folder to the Pi's smart_cane/models/ directory.")
    print("\nOn the Pi, load it the same way as a .pt file:")
    print('    YOLO("models/road_hazard_v1_ncnn_model")')
    print("\nBenchmark both (.pt vs ncnn) on the actual Pi 5 before committing —")
    print("export speedups vary by model/hardware, always verify on-device.")


if __name__ == "__main__":
    main()
