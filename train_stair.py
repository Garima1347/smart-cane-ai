from ultralytics import YOLO
if __name__ == "__main__":
    model = YOLO("yolo11n.pt")

    model.train(
        data="datasets/Stairs/data.yaml",
        epochs=50,
        imgsz=640,
        batch=8,
        device=0,
        workers=4,
        project="runs/smart_cane",
        name="stairs"
    )