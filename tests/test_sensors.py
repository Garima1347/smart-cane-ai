"""
Quick sanity tests — runnable on Mac with no hardware attached.
Run with:  python -m pytest tests/  (or just: python tests/test_sensors.py)
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.sensors.ultrasonic import MockUltrasonicSensor
from src.sensors.ground_detector import GroundHazardDetector
from src.navigation.obstacle_logic import build_alerts, format_distance_phrase, ClosingSpeedTracker


def test_mock_sensor_returns_valid_range():
    sensor = MockUltrasonicSensor(max_distance_cm=400)
    for _ in range(20):
        d = sensor.get_distance_cm()
        assert 0 <= d <= 400, f"Distance {d} out of expected range"
    print("test_mock_sensor_returns_valid_range: PASSED")


def test_danger_alert_triggers_when_close():
    detections = [{"label": "person", "confidence": 0.9, "direction": "center", "rough_distance": "near",
                   "bbox": (0, 0, 10, 10)}]
    alerts = build_alerts(detections, ultrasonic_distance_cm=30,
                           danger_distance_cm=60, warning_distance_cm=150)
    assert any(a["urgent"] for a in alerts), "Expected an urgent alert when distance is below danger threshold"
    assert "person" in alerts[0]["phrase"].lower()
    assert "meter" in alerts[0]["phrase"].lower(), "Distance should always be phrased in meters"
    print("test_danger_alert_triggers_when_close: PASSED")


def test_no_alert_when_far_and_no_detections():
    alerts = build_alerts([], ultrasonic_distance_cm=350,
                           danger_distance_cm=60, warning_distance_cm=150)
    assert alerts == [], "Expected no alerts when nothing is close and nothing detected"
    print("test_no_alert_when_far_and_no_detections: PASSED")


def test_side_detection_produces_warning_not_urgent():
    detections = [{"label": "chair", "confidence": 0.8, "direction": "left", "rough_distance": "near",
                   "bbox": (0, 0, 10, 10)}]
    alerts = build_alerts(detections, ultrasonic_distance_cm=None,
                           danger_distance_cm=60, warning_distance_cm=150)
    assert len(alerts) == 1
    assert alerts[0]["urgent"] is False
    assert "left" in alerts[0]["phrase"].lower()
    print("test_side_detection_produces_warning_not_urgent: PASSED")


def test_distance_phrasing_in_meters():
    assert format_distance_phrase(0.3) == "less than half a meter"
    assert format_distance_phrase(0.8) == "less than a meter"
    assert format_distance_phrase(2.3) == "2.3 meters"
    print("test_distance_phrasing_in_meters: PASSED")


def test_pothole_detection_after_calibration():
    gd = GroundHazardDetector(drop_threshold_cm=12, raise_threshold_cm=8, calibration_samples=10)
    for _ in range(10):
        gd.update(40.0)  # calibrate on flat ground
    assert gd.is_calibrated
    assert gd.check_hazard()["type"] is None

    gd.update(60.0)  # sudden drop-off
    hazard = gd.check_hazard()
    assert hazard["type"] == "hole"
    print("test_pothole_detection_after_calibration: PASSED")


def test_step_up_detection_after_calibration():
    gd = GroundHazardDetector(drop_threshold_cm=12, raise_threshold_cm=8, calibration_samples=10)
    for _ in range(10):
        gd.update(40.0)
    gd.update(28.0)  # sudden closer reading = curb/step
    hazard = gd.check_hazard()
    assert hazard["type"] == "step_up"
    print("test_step_up_detection_after_calibration: PASSED")


def test_ground_hazard_alert_is_urgent():
    alerts = build_alerts([], None, 60, 150, ground_hazard={"type": "hole", "deviation_cm": 20})
    assert alerts[0]["key"] == "ground_hole"
    assert alerts[0]["urgent"] is True
    print("test_ground_hazard_alert_is_urgent: PASSED")


def test_closing_speed_shortens_cooldown():
    tracker = ClosingSpeedTracker()
    t0 = time.time()
    tracker.update(200, t0)
    tracker.update(100, t0 + 1.0)  # 100cm/s closing speed = fast approach
    assert tracker.urgency_multiplier() < 1.0, "Fast approach should shrink the cooldown multiplier"
    print("test_closing_speed_shortens_cooldown: PASSED")


if __name__ == "__main__":
    test_mock_sensor_returns_valid_range()
    test_danger_alert_triggers_when_close()
    test_no_alert_when_far_and_no_detections()
    test_side_detection_produces_warning_not_urgent()
    test_distance_phrasing_in_meters()
    test_pothole_detection_after_calibration()
    test_step_up_detection_after_calibration()
    test_ground_hazard_alert_is_urgent()
    test_closing_speed_shortens_cooldown()
    print("\nAll tests passed.")
