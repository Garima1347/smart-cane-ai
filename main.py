#!/usr/bin/env python3
"""
Smart Navigation Cane — main entry point.

Runs on macOS (dev/testing, mocked hardware) and Raspberry Pi 5 (real
hardware) using the exact same code — platform is auto-detected.

Features:
  - YOLOv8 object detection (what's ahead + which direction)
  - Forward ultrasonic sensor (precise close-range distance, always spoken in meters)
  - Ground-facing ultrasonic sensor (pothole / drop-off / step-up detection)
  - Voice alerts (offline TTS) with smart cooldowns
  - Haptic (vibration motor) alerts as a silent backup channel
  - Emergency SOS button (long-press)
  - Walking-speed-adaptive alert timing (faster repeats when closing in fast)
  - CSV logging of every alert for later review

Usage:
    python main.py                        # normal run
    python main.py --no-camera            # ultrasonic + voice only, skip YOLO
    python main.py --interactive-sensor    # Mac: type distances manually to test
    python main.py --show-preview          # show OpenCV window with boxes (debug)
    python main.py --config custom.yaml
"""

import argparse
import signal
import sys
import time

import cv2
import yaml

from src.utils.logger import setup_logger
from src.utils.platform_utils import PLATFORM
from src.utils.data_logger import DataLogger
from src.vision.camera import create_camera
from src.vision.camera_stream import ThreadedCameraStream
from src.vision.detector import ObjectDetector
from src.sensors.sensor_manager import SensorManager
from src.sensors.ground_detector import GroundHazardDetector
from src.sensors.sos_button import create_sos_button
from src.audio.voice_alert import VoiceEngine
from src.audio.alert_manager import AlertManager
from src.audio.haptic import create_haptic_engine
from src.navigation.obstacle_logic import build_alerts, ClosingSpeedTracker


def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="Smart Navigation Cane")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--no-camera", action="store_true", help="Skip YOLO/camera, ultrasonic+voice only")
    parser.add_argument("--interactive-sensor", action="store_true",
                         help="Mac only: type a distance value to manually test alerts")
    parser.add_argument("--show-preview", action="store_true", help="Show OpenCV debug window with boxes")
    args = parser.parse_args()

    cfg = load_config(args.config)

    logger = setup_logger(
        level=cfg["logging"]["level"],
        log_to_file=cfg["logging"]["log_to_file"],
        log_file=cfg["logging"]["log_file"],
    )
    logger.info(f"Starting Smart Cane on platform: {PLATFORM}")

    # --- Data logger (obstacle/alert CSV history) ---
    data_logger = None
    if cfg["logging"].get("log_obstacles_csv", True):
        data_logger = DataLogger(filepath=cfg["logging"].get("obstacle_log_file", "obstacle_log.csv"))

    # --- Voice engine ---
    voice_engine = VoiceEngine(
        rate=cfg["voice"]["rate"],
        volume=cfg["voice"]["volume"],
        voice_id=cfg["voice"]["voice_id"],
    )

    # --- Haptic engine (vibration motor / mock on Mac) ---
    haptic_cfg = cfg.get("haptic", {})
    haptic_engine = create_haptic_engine(
        pin=haptic_cfg.get("pin") if haptic_cfg.get("enabled", False) else None
    )

    # --- Alert manager ties voice + haptic + logging together ---
    alert_manager = AlertManager(
        voice_engine=voice_engine,
        cooldown_seconds=cfg["alerts"]["cooldown_seconds"],
        urgent_cooldown_seconds=cfg["alerts"]["urgent_cooldown_seconds"],
        haptic_engine=haptic_engine,
        data_logger=data_logger,
    )
    voice_engine.speak("Smart cane starting up.")

    # --- Forward + ground ultrasonic sensors ---
    sensor_cfgs = [cfg["sensors"]["forward"]]
    ground_enabled = cfg["sensors"].get("ground", {}).get("enabled", False)
    if ground_enabled:
        sensor_cfgs.append(cfg["sensors"]["ground"])

    sensor_manager = SensorManager(
        sensor_configs=sensor_cfgs,
        poll_interval=0.1,
        interactive=args.interactive_sensor,
    )
    sensor_manager.start()

    ground_detector = None
    if ground_enabled:
        g_cfg = cfg["sensors"]["ground"]
        ground_detector = GroundHazardDetector(
            drop_threshold_cm=g_cfg["drop_threshold_cm"],
            raise_threshold_cm=g_cfg["raise_threshold_cm"],
            calibration_samples=g_cfg["calibration_samples"],
        )
        voice_engine.speak("Calibrating ground sensor. Please stand on flat ground.")

    # --- Closing-speed tracker (adaptive alert timing) ---
    speed_tracker = ClosingSpeedTracker()
    adaptive_speed = cfg["alerts"].get("adaptive_speed_cooldown", True)

    # --- SOS button ---
    sos_cfg = cfg.get("sos_button", {})
    sos_button = None
    if sos_cfg.get("enabled", False) and not (args.interactive_sensor and PLATFORM != "raspberry_pi"):
        # On Mac, both --interactive-sensor and the keyboard SOS substitute
        # read from stdin — they can't run at once. Interactive sensor mode
        # wins since it's the more common testing scenario; the SOS button
        # is unaffected on the real Pi hardware (uses a physical GPIO pin).
        sos_button = create_sos_button(pin=sos_cfg.get("pin"), hold_seconds=sos_cfg.get("hold_seconds", 2.0))

        def handle_sos():
            logger.warning("SOS TRIGGERED by user.")
            voice_engine.clear_queue()
            voice_engine.speak("Emergency alert activated. Help needed.")
            if haptic_engine:
                haptic_engine.pulse_pattern("danger")
            if data_logger:
                data_logger.log_alert("sos_triggered", "Emergency alert activated.", True, None)

        sos_button.start(handle_sos)

    # --- Vision (optional) ---
    camera = None
    detector = None
    if not args.no_camera:
        try:
            raw_camera = create_camera(
                index=cfg["vision"]["camera_index"],
                width=cfg["vision"]["frame_width"],
                height=cfg["vision"]["frame_height"],
                prefer_picamera=cfg["vision"]["use_picamera_on_pi"],
            )
            if cfg["vision"].get("threaded_capture", True):
                camera = ThreadedCameraStream(raw_camera).start()
            else:
                camera = raw_camera

            detector = ObjectDetector(
            models=cfg["vision"]["models"],
            confidence_threshold=cfg["vision"]["confidence_threshold"],
            inference_size=cfg["vision"]["inference_size"],
            )
            voice_engine.speak("Camera and detection ready.")
        except Exception as e:
            logger.error(f"Camera/YOLO init failed, continuing with ultrasonic-only mode: {e}")
            camera = None
            detector = None

    # --- Graceful shutdown handling ---
    running = {"flag": True}

    def handle_sigint(sig, frame):
        logger.info("Shutdown signal received, stopping...")
        running["flag"] = False

    signal.signal(signal.SIGINT, handle_sigint)

    frame_count = 0
    frame_skip = cfg["vision"]["frame_skip"]
    danger_cm = cfg["alerts"]["danger_distance_cm"]
    warning_cm = cfg["alerts"]["warning_distance_cm"]

    fps_window_start = time.time()
    fps_frame_counter = 0

    try:
        while running["flag"]:
            loop_start = time.time()
            detections = []

            # --- Vision step ---
            if camera and detector:
                success, frame = camera.read()
                if success and frame is not None:
                    frame_count += 1
                    if frame_count % frame_skip == 0:
                        detections = detector.detect(frame)
                        fps_frame_counter += 1

                    if args.show_preview:
                        _draw_preview(frame, detections)
                        cv2.imshow("Smart Cane Debug", frame)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            break

            # --- Sensor step ---
            forward_distance = sensor_manager.get_latest("front")
            speed_tracker.update(forward_distance, loop_start)
            speed_multiplier = speed_tracker.urgency_multiplier() if adaptive_speed else 1.0

            ground_hazard = None
            if ground_detector:
                ground_reading = sensor_manager.get_latest("ground")
                ground_detector.update(ground_reading)
                ground_hazard = ground_detector.check_hazard()

            # --- Fusion + alerts ---
            alerts = build_alerts(
                detections=detections,
                ultrasonic_distance_cm=forward_distance,
                danger_distance_cm=danger_cm,
                warning_distance_cm=warning_cm,
                ground_hazard=ground_hazard,
            )

            fired_keys = set()
            for a in alerts:
                fired = alert_manager.trigger(
                    a["key"], a["phrase"], urgent=a["urgent"],
                    haptic=a.get("haptic", "off"), distance_m=a.get("distance_m"),
                    speed_multiplier=speed_multiplier,
                )
                if fired:
                    fired_keys.add(a["key"])
            alert_manager.clear_haptic_if_idle(fired_keys)

            # --- Periodic FPS log (every ~5s) for performance tuning on Pi ---
            if time.time() - fps_window_start >= 5.0:
                elapsed = time.time() - fps_window_start
                logger.debug(f"Detection FPS: {fps_frame_counter / elapsed:.1f}")
                fps_window_start = time.time()
                fps_frame_counter = 0

            time.sleep(0.03)  # small yield; sensors/camera have their own pacing

    finally:
        logger.info("Cleaning up...")
        sensor_manager.stop()
        if camera:
            camera.release()
        if sos_button:
            sos_button.stop()
        if haptic_engine:
            haptic_engine.stop()
        if args.show_preview:
            cv2.destroyAllWindows()

        if data_logger:
            summary = data_logger.session_summary()
            voice_engine.speak(
                f"Session ended. {summary['total']} alerts, {summary['urgent']} urgent."
            )
        else:
            voice_engine.speak("Smart cane shutting down.")

        time.sleep(2.0)  # let the final phrase finish before killing the thread
        voice_engine.stop()
        logger.info("Shutdown complete.")
        sys.exit(0)


def _draw_preview(frame, detections):
    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"{det['label']} {det['confidence']:.2f} {det['direction']}/{det['rough_distance']}"
        cv2.putText(frame, label, (x1, max(0, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)


if __name__ == "__main__":
    main()
