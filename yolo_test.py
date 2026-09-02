import cv2

import time

import threading

import pyttsx3

from ultralytics import YOLO





# ============================================================

# SETTINGS

# ============================================================

MODEL_PATH = r".\smart-cane-ai\runs\detect\train_door\weights\best.pt"

# VERY LOW for testing

CONFIDENCE = 0.01

# Voice can repeat every 2 seconds

VOICE_COOLDOWN = 2





# ============================================================

# VOICE

# ============================================================

def speak(text):

    try:

        engine = pyttsx3.init()

        engine.setProperty("rate", 150)

        engine.say(text)

        engine.runAndWait()

        engine.stop()

    except Exception as e:

        print("VOICE ERROR:", e)





# ============================================================

# LOAD MODEL

# ============================================================

print()

print("==========================================")

print("SMART CANE - LIVE DOOR DETECTION")

print("==========================================")

print()

print("Loading model...")

model = YOLO(MODEL_PATH)

print("MODEL LOADED")

print("Classes:", model.names)

print()

print("Opening camera...")





# ============================================================

# CAMERA

# ============================================================

camera = cv2.VideoCapture(0)

if not camera.isOpened():

    print("ERROR: CAMERA NOT OPENED")

    input("Press Enter to exit...")

    exit()





# Try to force a normal webcam resolution

camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)

camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

print("CAMERA OPENED!")

print()

print("SHOW YOUR DOOR DIRECTLY TO THE CAMERA.")

print()

print("CONFIDENCE:", CONFIDENCE)

print()

print("Press ESC to close.")

print()





# ============================================================

# WINDOW

# ============================================================

window_name = "SMART CANE - LIVE DOOR DETECTION"

cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

cv2.resizeWindow(window_name, 1000, 750)





# ============================================================

# VARIABLES

# ============================================================

last_voice_time = 0

frame_number = 0

last_detection_print = 0





# ============================================================

# MAIN LOOP

# ============================================================

while True:

    success, frame = camera.read()

    if not success:

        print("ERROR: Could not read camera frame.")

        break





    frame_number += 1





    # --------------------------------------------------------

    # YOLO

    # --------------------------------------------------------

    results = model.predict(

        source=frame,

        conf=CONFIDENCE,

        verbose=False

    )

    result = results[0]





    # --------------------------------------------------------

    # DETECTIONS

    # --------------------------------------------------------

    detections = []





    if result.boxes is not None:

        for box in result.boxes:

            confidence = float(box.conf[0])

            class_id = int(box.cls[0])

            class_name = model.names[class_id]





            if class_name.lower() == "door":

                x1, y1, x2, y2 = map(

                    int,

                    box.xyxy[0].tolist()

                )





                detections.append(

                    {

                        "confidence": confidence,

                        "x1": x1,

                        "y1": y1,

                        "x2": x2,

                        "y2": y2

                    }

                )





    # --------------------------------------------------------

    # PRINT STATUS EVERY 30 FRAMES

    # --------------------------------------------------------

    if frame_number % 30 == 0:

        print(

            "Frame:",

            frame_number,

            "| Doors detected:",

            len(detections)

        )





    # ========================================================

    # DOOR FOUND

    # ========================================================

    if len(detections) > 0:

        # strongest detection

        detections.sort(

            key=lambda d: d["confidence"],

            reverse=True

        )

        best = detections[0]

        confidence = best["confidence"]

        x1 = best["x1"]

        y1 = best["y1"]

        x2 = best["x2"]

        y2 = best["y2"]





        # ----------------------------------------------------

        # DRAW EVERY DOOR

        # ----------------------------------------------------

        for d in detections:

            cv2.rectangle(

                frame,

                (d["x1"], d["y1"]),

                (d["x2"], d["y2"]),

                (0, 255, 0),

                3

            )

            cv2.putText(

                frame,

                f"DOOR {d['confidence']:.2f}",

                (

                    d["x1"],

                    max(d["y1"] - 10, 25)

                ),

                cv2.FONT_HERSHEY_SIMPLEX,

                0.7,

                (0, 255, 0),

                2

            )





        # ----------------------------------------------------

        # POSITION

        # ----------------------------------------------------

        height, width = frame.shape[:2]

        center_x = (x1 + x2) // 2





        if center_x < width * 0.33:

            position = "LEFT"

        elif center_x > width * 0.66:

            position = "RIGHT"

        else:

            position = "CENTER"





        # ----------------------------------------------------

        # SCREEN MESSAGE

        # ----------------------------------------------------

        cv2.putText(

            frame,

            "DOOR DETECTED!",

            (20, 45),

            cv2.FONT_HERSHEY_SIMPLEX,

            1.2,

            (0, 255, 0),

            3

        )

        cv2.putText(

            frame,

            f"Confidence: {confidence:.2f}",

            (20, 85),

            cv2.FONT_HERSHEY_SIMPLEX,

            0.8,

            (0, 255, 0),

            2

        )

        cv2.putText(

            frame,

            f"Position: {position}",

            (20, 120),

            cv2.FONT_HERSHEY_SIMPLEX,

            0.8,

            (0, 255, 0),

            2

        )





        # ----------------------------------------------------

        # TERMINAL

        # ----------------------------------------------------

        if time.time() - last_detection_print > 2:

            print()

            print(

                "======================================"

            )

            print(

                "DOOR DETECTED!"

            )

            print(

                "Confidence:",

                round(confidence, 3)

            )

            print(

                "Position:",

                position

            )

            print(

                "Number of doors:",

                len(detections)

            )

            print(

                "======================================"

            )

            last_detection_print = time.time()





        # ----------------------------------------------------

        # VOICE

        # ----------------------------------------------------

        current_time = time.time()





        if current_time - last_voice_time >= VOICE_COOLDOWN:

            voice_text = f"Door detected {position}"

            print(

                "VOICE:",

                voice_text

            )





            threading.Thread(

                target=speak,

                args=(voice_text,),

                daemon=True

            ).start()





            last_voice_time = current_time





    # ========================================================

    # NO DOOR

    # ========================================================

    else:

        cv2.putText(

            frame,

            "NO DOOR DETECTED",

            (20, 45),

            cv2.FONT_HERSHEY_SIMPLEX,

            1.2,

            (0, 0, 255),

            3

        )

        cv2.putText(

            frame,

            "Move camera toward a door",

            (20, 85),

            cv2.FONT_HERSHEY_SIMPLEX,

            0.8,

            (0, 0, 255),

            2

        )





    # ========================================================

    # SHOW CAMERA

    # ========================================================

    cv2.imshow(

        window_name,

        frame

    )





    # ========================================================

    # KEYBOARD

    # ========================================================

    key = cv2.waitKey(1) & 0xFF





    if key == 27:

        print()

        print("ESC pressed.")

        break





# ============================================================

# CLOSE

# ============================================================

camera.release()

cv2.destroyAllWindows()

print()

print("Camera closed.")

print("Program finished.")