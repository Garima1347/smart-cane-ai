"""
Fuses all sensor inputs into a short list of spoken/haptic alerts each cycle:
  - Forward ultrasonic sensor  -> precise close-range distance (always
    reported in METERS in spoken phrases)
  - Ground (downward) ultrasonic sensor -> pothole / drop-off / step-up
  - YOLO detections            -> what the obstacle is + left/center/right

Design:
  - The forward ultrasonic distance is the primary "urgency" signal since
    it's precise and fast — if something is within danger_distance_m, that
    ALWAYS produces an urgent alert, even if YOLO doesn't recognize what it
    is (a wall, a pole, a parked bike — things YOLO may miss but the user
    still needs to know about).
  - Ground hazards (potholes, step-ups) are checked independently and
    ALWAYS urgent — a hole underfoot is arguably the single most dangerous
    thing this system detects, more so than a person a meter away.
  - YOLO detections add *identity and direction* on top of that: "person
    ahead" is more useful than just "obstacle ahead."
  - Closing speed (how fast the forward distance is shrinking) shortens the
    alert cooldown — if you're walking briskly toward something, you need
    faster-repeating warnings than if you're standing still near it.
"""

import logging
from collections import deque

logger = logging.getLogger("smart_cane")


def cm_to_m(cm: float) -> float:
    return cm / 100.0


def format_distance_phrase(distance_m: float) -> str:
    """Always phrases distance in meters, human-friendly rounding."""
    if distance_m < 0.5:
        return "less than half a meter"
    elif distance_m < 1.0:
        return "less than a meter"
    else:
        return f"{distance_m:.1f} meters"


class ClosingSpeedTracker:
    """
    Tracks recent forward-distance readings to estimate whether the user is
    approaching an obstacle quickly, moderately, or standing still/moving
    away. Used to tighten alert cooldowns when closing fast — the single
    biggest real-world safety improvement over a fixed cooldown.
    """

    def __init__(self, history_size: int = 6):
        self._history = deque(maxlen=history_size)  # (timestamp, distance_cm)

    def update(self, distance_cm: float, timestamp: float):
        if distance_cm is not None:
            self._history.append((timestamp, distance_cm))

    def closing_speed_cm_per_s(self) -> float:
        """Positive = getting closer (distance shrinking). Negative = moving away."""
        if len(self._history) < 2:
            return 0.0
        t0, d0 = self._history[0]
        t1, d1 = self._history[-1]
        dt = t1 - t0
        if dt <= 0:
            return 0.0
        return (d0 - d1) / dt  # cm/s, positive when shrinking

    def urgency_multiplier(self) -> float:
        """
        Returns a cooldown multiplier: <1.0 means "shorten the cooldown"
        (repeat alerts faster) because the user is closing in quickly.
        """
        speed = self.closing_speed_cm_per_s()
        if speed > 80:      # fast approach (~brisk walk directly at something)
            return 0.4
        elif speed > 30:    # moderate approach
            return 0.7
        else:
            return 1.0


def build_alerts(detections: list, ultrasonic_distance_cm: float,
                  danger_distance_cm: float, warning_distance_cm: float,
                  ground_hazard: dict = None) -> list:
    """
    Returns a list of alert dicts, ordered by priority (most urgent first):
      {"key": str, "phrase": str, "urgent": bool, "haptic": "danger"|"warning"|"off",
       "distance_m": float|None}
    """
    alerts = []

    # --- 1. Ground hazards (pothole / step-up) — checked first, always urgent ---
    if ground_hazard and ground_hazard.get("type"):
        if ground_hazard["type"] == "hole":
            alerts.append({
                "key": "ground_hole", "urgent": True, "haptic": "danger",
                "distance_m": None,
                "phrase": "Stop. Hole or drop ahead. Step carefully.",
            })
        elif ground_hazard["type"] == "step_up":
            alerts.append({
                "key": "ground_step_up", "urgent": True, "haptic": "danger",
                "distance_m": None,
                "phrase": "Caution. Step up or curb ahead.",
            })

    # --- 2. Forward ultrasonic urgency (hardware-confirmed distance) ---
    if ultrasonic_distance_cm is not None:
        distance_m = cm_to_m(ultrasonic_distance_cm)

        if ultrasonic_distance_cm <= danger_distance_cm:
            label = _closest_center_label(detections)
            phrase = f"Stop. {label + ' ' if label else ''}{format_distance_phrase(distance_m)} ahead."
            alerts.append({"key": "danger_front", "phrase": phrase, "urgent": True,
                            "haptic": "danger", "distance_m": distance_m})

        elif ultrasonic_distance_cm <= warning_distance_cm:
            label = _closest_center_label(detections)
            phrase = f"Caution, {label + ' ' if label else 'obstacle '}{format_distance_phrase(distance_m)} ahead."
            alerts.append({"key": "warning_front", "phrase": phrase, "urgent": False,
                            "haptic": "warning", "distance_m": distance_m})

    # --- 3. Vision-driven alerts for things off to the side (not covered by forward sensor) ---
    for det in detections:
        if det["direction"] == "center":
            continue  # already covered by ultrasonic-driven alert above
        if det["rough_distance"] not in ("near", "medium"):
            continue  # too far away to matter yet

        key = f"{det['label']}_{det['direction']}"
        phrase = f"{det['label'].capitalize()} on your {det['direction']}."
        alerts.append({"key": key, "phrase": phrase, "urgent": False,
                        "haptic": "off", "distance_m": None})

    return alerts


def _closest_center_label(detections: list):
    """Find the label of the nearest 'center' detection, if any, to enrich the phrase."""
    center_dets = [d for d in detections if d["direction"] == "center"]
    if not center_dets:
        return None

    order = {"near": 0, "medium": 1, "far": 2}
    center_dets.sort(key=lambda d: order.get(d["rough_distance"], 3))
    return center_dets[0]["label"]
