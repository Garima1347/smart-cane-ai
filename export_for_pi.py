#!/usr/bin/env python3

"""
Export a trained YOLO model to NCNN format for Raspberry Pi 5.

The model is trained on the laptop as a normal .pt file and then
exported to NCNN for faster CPU inference on Raspberry Pi.

Usage:
    python training/export_for_pi.py --weights models/stairs/best.pt

Examples:
    python training/export_for_pi.py --weights models/stairs/best.pt
    python training/export_for_pi.py --weights models/pothole/best.pt
    python training/export_for_pi.py --weights models/door/best.pt

The exported NCNN folder will be created next to the .pt model.
"""

import argparse
from pathlib import Path

from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser(
        description="Export a trained YOLO model to NCNN for Raspberry Pi 5"
    )

    parser.add_argument(
        "--weights",
        required=True,
        help="Path to the trained YOLO .pt model"
    )

    parser.add_argument(
        "--imgsz",
        type=int,
        default=320,
        help="Image size for inference/export (default: 320)"
    )

    args = parser.parse_args()

    # Check that the model exists
    weights_path = Path(args.weights)

    if not weights_path.exists():
        raise FileNotFoundError(
            f"Model not found: {weights_path}"
        )

    print("=" * 60)
    print("YOLO → NCNN Export for Raspberry Pi 5")
    print("=" * 60)

    print(f"Model : {weights_path}")
    print(f"Image size : {args.imgsz}")
    print()

    # Load trained YOLO model
    model = YOLO(str(weights_path))

    print("Model classes:")
    print(model.names)
    print()

    # Export to NCNN
    print("Exporting model to NCNN...")
    
    exported_path = model.export(
        format="ncnn",
        imgsz=args.imgsz
    )

    print()
    print("=" * 60)
    print("Export completed successfully!")
    print("=" * 60)

    print(f"NCNN model: {exported_path}")

    print()
    print("Copy this NCNN model folder to your Raspberry Pi.")

    print()
    print("On Raspberry Pi, load it with:")
    print(f'YOLO("{exported_path}")')

if __name__ == "__main__":
    main()