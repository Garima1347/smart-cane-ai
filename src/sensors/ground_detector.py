"""
Ground-facing ultrasonic hazard detection.

Detects:
    - holes / drops
    - steps / raised surfaces

The detector uses:
    - stable startup calibration
    - a rolling history
    - consecutive confirmations
    - controlled baseline adaptation

This prevents one noisy ultrasonic reading from triggering
an emergency ground alert.
"""

import logging
from collections import deque

logger = logging.getLogger("smart_cane")


class GroundHazardDetector:
    def __init__(
        self,
        drop_threshold_cm: float = 12.0,
        raise_threshold_cm: float = 8.0,
        calibration_samples: int = 30,
        history_size: int = 10,
        confirmation_samples: int = 3,
        baseline_adaptation_rate: float = 0.02,
    ):
        if drop_threshold_cm <= 0:
            raise ValueError("drop_threshold_cm must be greater than 0")

        if raise_threshold_cm <= 0:
            raise ValueError("raise_threshold_cm must be greater than 0")

        if calibration_samples < 3:
            raise ValueError("calibration_samples must be at least 3")

        if history_size < 1:
            raise ValueError("history_size must be at least 1")

        if confirmation_samples < 1:
            raise ValueError("confirmation_samples must be at least 1")

        if not 0.0 < baseline_adaptation_rate <= 1.0:
            raise ValueError(
                "baseline_adaptation_rate must be between 0 and 1"
            )

        self.drop_threshold_cm = float(drop_threshold_cm)
        self.raise_threshold_cm = float(raise_threshold_cm)
        self.calibration_samples = calibration_samples
        self.confirmation_samples = confirmation_samples
        self.baseline_adaptation_rate = baseline_adaptation_rate

        self._baseline = None
        self._calibration_buffer = []

        self._history = deque(maxlen=history_size)

        # Number of consecutive samples supporting each hazard.
        self._hole_confirmation_count = 0
        self._step_confirmation_count = 0

    def update(self, reading_cm):
        """
        Add one new physical ground-sensor reading.

        Invalid or missing readings are ignored.
        """
        if reading_cm is None:
            return

        try:
            reading_cm = float(reading_cm)
        except (TypeError, ValueError):
            return

        if reading_cm <= 0:
            return

        self._history.append(reading_cm)

        # ---------------------------------------------------------
        # Startup calibration
        # ---------------------------------------------------------
        if self._baseline is None:
            self._calibration_buffer.append(reading_cm)

            if len(self._calibration_buffer) >= self.calibration_samples:
                self._baseline = self._calculate_stable_baseline(
                    self._calibration_buffer
                )

                logger.info(
                    "Ground sensor calibrated. Baseline: %.1f cm",
                    self._baseline,
                )

            return

        # ---------------------------------------------------------
        # Baseline adaptation
        #
        # Only adapt when the current reading is close to the
        # established baseline. This prevents a hole/step from
        # permanently changing the baseline.
        # ---------------------------------------------------------
        deviation = reading_cm - self._baseline

        if abs(deviation) < self.raise_threshold_cm:
            self._baseline = (
                (1.0 - self.baseline_adaptation_rate) * self._baseline
                + self.baseline_adaptation_rate * reading_cm
            )

    def check_hazard(self):
        """
        Return a confirmed ground hazard.

        A single abnormal reading is not enough.

        Returns:
            {
                "type": "hole" | "step_up" | None,
                "deviation_cm": float
            }
        """
        if self._baseline is None or not self._history:
            self._reset_confirmation()
            return {
                "type": None,
                "deviation_cm": 0.0,
            }

        latest = self._history[-1]
        deviation = latest - self._baseline

        # ---------------------------------------------------------
        # Hole / drop detection
        # ---------------------------------------------------------
        if deviation >= self.drop_threshold_cm:
            self._hole_confirmation_count += 1
            self._step_confirmation_count = 0

            if self._hole_confirmation_count >= self.confirmation_samples:
                return {
                    "type": "hole",
                    "deviation_cm": deviation,
                }

        # ---------------------------------------------------------
        # Step-up detection
        # ---------------------------------------------------------
        elif deviation <= -self.raise_threshold_cm:
            self._step_confirmation_count += 1
            self._hole_confirmation_count = 0

            if self._step_confirmation_count >= self.confirmation_samples:
                return {
                    "type": "step_up",
                    "deviation_cm": abs(deviation),
                }

        # ---------------------------------------------------------
        # Normal reading
        # ---------------------------------------------------------
        else:
            self._reset_confirmation()

        return {
            "type": None,
            "deviation_cm": deviation,
        }

    @staticmethod
    def _calculate_stable_baseline(samples):
        """
        Calculate a robust baseline.

        Instead of trusting one average directly, remove the lowest
        and highest 10% of readings when enough samples are available.
        This reduces the effect of startup noise/outliers.
        """
        values = sorted(float(value) for value in samples)

        if len(values) < 10:
            return sum(values) / len(values)

        trim_count = max(1, int(len(values) * 0.10))

        trimmed = values[trim_count:-trim_count]

        if not trimmed:
            trimmed = values

        return sum(trimmed) / len(trimmed)

    def _reset_confirmation(self):
        self._hole_confirmation_count = 0
        self._step_confirmation_count = 0

    @property
    def is_calibrated(self):
        return self._baseline is not None

    @property
    def baseline_cm(self):
        return self._baseline

    def recalibrate(self):
        """
        Reset calibration and hazard confirmation state.
        """
        self._baseline = None
        self._calibration_buffer = []
        self._history.clear()
        self._reset_confirmation()

        logger.info("Ground sensor calibration reset.")