"""
Haptic (vibration motor) feedback — a silent alert channel that works
alongside voice. This matters a lot in practice: busy streets, traffic
noise, or a user wearing headphones for other reasons can all drown out
spoken alerts, but a vibration in the cane handle still gets through.

Hardware: a small coin/pancake vibration motor driven through a transistor
(the GPIO pin can't source enough current directly — see README wiring
section), connected to a PWM-capable GPIO pin. Pulse pattern intensity
scales with urgency:
  - Danger (very close / pothole)  -> fast, near-continuous pulsing
  - Warning (approaching)          -> slower, distinct pulses
  - Off                            -> no vibration

On macOS (no GPIO), this becomes a no-op that just logs what it *would*
have done — so the same main.py code path works on both platforms without
special-casing.
"""

import logging
import threading
import time

from src.utils.platform_utils import IS_PI

logger = logging.getLogger("smart_cane")


class BaseHapticEngine:
    def pulse_pattern(self, pattern: str):
        raise NotImplementedError

    def stop(self):
        pass


class RealHapticEngine(BaseHapticEngine):
    """Drives a real vibration motor via a PWM-capable GPIO pin (gpiozero + lgpio)."""

    def __init__(self, pin: int):
        from gpiozero import PWMOutputDevice
        from gpiozero.pins.lgpio import LGPIOFactory

        self.motor = PWMOutputDevice(pin, pin_factory=LGPIOFactory())
        self._stop_event = threading.Event()
        self._thread = None
        logger.info(f"Haptic motor initialized on GPIO{pin}")

    def pulse_pattern(self, pattern: str):
        self._stop_current()
        if pattern == "off":
            return

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_pattern, args=(pattern, self._stop_event), daemon=True)
        self._thread.start()

    def _run_pattern(self, pattern: str, stop_event: threading.Event):
        specs = {
            "danger": (1.0, 0.08, 0.05),   # (intensity, on_time, off_time) — fast buzz
            "warning": (0.6, 0.15, 0.35),  # slower, gentler pulses
        }
        intensity, on_t, off_t = specs.get(pattern, (0.5, 0.1, 0.3))

        while not stop_event.is_set():
            self.motor.value = intensity
            time.sleep(on_t)
            self.motor.value = 0
            time.sleep(off_t)

    def _stop_current(self):
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=0.5)
        self.motor.value = 0

    def stop(self):
        self._stop_current()
        self.motor.close()


class MockHapticEngine(BaseHapticEngine):
    """No hardware on Mac — just logs what would have vibrated, for dev visibility."""

    def __init__(self):
        self._last_pattern = None
        logger.info("Mock haptic engine active (no vibration hardware — simulated)")

    def pulse_pattern(self, pattern: str):
        if pattern != self._last_pattern:
            logger.debug(f"[HAPTIC SIM] pattern -> {pattern}")
            self._last_pattern = pattern


def create_haptic_engine(pin: int = None):
    if IS_PI and pin is not None:
        try:
            return RealHapticEngine(pin)
        except Exception as e:
            logger.warning(f"Haptic motor init failed ({e}), continuing without vibration feedback.")
    return MockHapticEngine()
