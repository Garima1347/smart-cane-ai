"""
Ground hazard detection — potholes, curbs, drop-offs (missing steps, ditches)
and step-ups, using a SECOND ultrasonic sensor mounted facing down and
slightly forward on the cane (roughly 30-45 degrees off vertical, aimed
~50-70cm ahead of the tip).

How it works:
  On flat ground, the downward sensor reads a stable "baseline" distance to
  the ground (calibrated automatically in the first few seconds of running,
  and continuously re-averaged while the reading is stable). Any *sudden*
  deviation from that baseline means the ground ahead isn't flat:

    - Reading much LARGER than baseline  -> a hole, drop-off, missing step,
      or downward staircase. This is the most dangerous case for a cane
      user and gets an urgent alert.
    - Reading much SMALLER than baseline -> a raised curb, step up, or
      obstacle on the ground directly ahead.

This is the same basic principle real assistive-cane research prototypes
use (e.g. "smart cane" IoT projects with a second downward IR/ultrasonic
sensor) — it's a cheap, reliable, low-latency way to catch hazards that a
camera struggles with (potholes are low-contrast and easy for YOLO to miss
entirely, since it's not a class YOLO is trained on).
"""

import logging
import time
from collections import deque

logger = logging.getLogger("smart_cane")


class GroundHazardDetector:
    def __init__(self, drop_threshold_cm: float = 12.0, raise_threshold_cm: float = 8.0,
                 calibration_samples: int = 30, history_size: int = 10):
        """
        drop_threshold_cm: how much FARTHER than baseline counts as a hole/drop-off.
        raise_threshold_cm: how much CLOSER than baseline counts as a step-up/curb.
        calibration_samples: readings used to establish the initial flat-ground baseline.
        """
        self.drop_threshold_cm = drop_threshold_cm
        self.raise_threshold_cm = raise_threshold_cm
        self.calibration_samples = calibration_samples

        self._baseline = None
        self._calibration_buffer = []
        self._history = deque(maxlen=history_size)

    def update(self, reading_cm: float):
        """Feed a new downward-sensor reading. Call this every poll cycle."""
        if reading_cm is None:
            return

        self._history.append(reading_cm)

        if self._baseline is None:
            self._calibration_buffer.append(reading_cm)
            if len(self._calibration_buffer) >= self.calibration_samples:
                self._baseline = sum(self._calibration_buffer) / len(self._calibration_buffer)
                logger.info(f"Ground sensor calibrated: baseline={self._baseline:.1f}cm")
            return

        # Slowly drift the baseline to track gradual terrain changes (e.g. walking
        # onto a gentle slope), but only while readings look "normal" — a sudden
        # spike/drop should NOT get absorbed into the baseline, or we'd miss it.
        deviation = reading_cm - self._baseline
        if abs(deviation) < self.raise_threshold_cm:
            self._baseline = 0.98 * self._baseline + 0.02 * reading_cm

    def check_hazard(self) -> dict:
        """
        Returns {"type": "hole"|"step_up"|None, "deviation_cm": float}
        Requires calibration to be complete; returns type=None until then.
        """
        if self._baseline is None or not self._history:
            return {"type": None, "deviation_cm": 0.0}

        latest = self._history[-1]
        deviation = latest - self._baseline

        if deviation >= self.drop_threshold_cm:
            return {"type": "hole", "deviation_cm": deviation}
        elif deviation <= -self.raise_threshold_cm:
            return {"type": "step_up", "deviation_cm": abs(deviation)}
        else:
            return {"type": None, "deviation_cm": deviation}

    @property
    def is_calibrated(self) -> bool:
        return self._baseline is not None

    def recalibrate(self):
        """Force re-calibration (e.g. call this if the user starts on uneven ground)."""
        self._baseline = None
        self._calibration_buffer = []
        logger.info("Ground sensor recalibration requested.")
