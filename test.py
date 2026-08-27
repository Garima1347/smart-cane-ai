from ultralytics import YOLO

model = YOLO("runs/detect/runs/smart_cane/stairs-4/weights/best.pt")

model.predict(
    source="test_images",
    conf=0.5,
    device=0,
    save=True
)