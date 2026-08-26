"""
HC-SR04 ultrasonic distance sensor.

IMPORTANT (Pi 5 specific): the old `RPi.GPIO` library does NOT reliably
support the Raspberry Pi 5's new RP1 I/O chip. We use `gpiozero` with the
`lgpio` pin factory instead, which does support Pi 5. This is installed by
scripts/setup_pi.sh.

On macOS (no GPIO hardware), a MockUltrasonicSensor is used instead, which
simulates a slowly varying distance so you can test the full alert pipeline
without any hardware. There's also an InteractiveMockSensor you can type
distances into from the terminal for manual testing.
"""

import logging
import random
import time
import threading

from src.utils.platform_utils import IS_PI

logger = logging.getLogger("smart_cane")


class BaseUltrasonicSensor:
    def get_distance_cm(self) -> float:
        raise NotImplementedError

    def close(self):
        pass


class RealUltrasonicSensor(BaseUltrasonicSensor):
    """Real HC-SR04 sensor on Raspberry Pi 5 GPIO, via gpiozero + lgpio."""

    def __init__(self, trig_pin: int, echo_pin: int, max_distance_cm: int = 400):
        from gpiozero import DistanceSensor
        from gpiozero.pins.lgpio import LGPIOFactory

        self.sensor = DistanceSensor(
            echo=echo_pin,
            trigger=trig_pin,
            max_distance=max_distance_cm / 100.0,  # gpiozero uses meters
            pin_factory=LGPIOFactory(),
        )
        logger.info(f"Real HC-SR04 sensor initialized (TRIG={trig_pin}, ECHO={echo_pin})")

    def get_distance_cm(self) -> float:
        # gpiozero returns meters; convert to cm.
        return self.sensor.distance * 100.0

    def close(self):
        self.sensor.close()


class MockUltrasonicSensor(BaseUltrasonicSensor):
    """
    Simulates a distance sensor for testing on Mac. Distance drifts slowly
    and occasionally dips close (simulating an approaching obstacle) so you
    can see danger-level alerts trigger too.
    """

    def __init__(self, max_distance_cm: int = 400, name: str = "front"):
        self._distance = 200.0
        self.max_distance_cm = max_distance_cm
        self.name = name
        logger.info(f"Mock ultrasonic sensor '{name}' active (no real hardware — simulated data)")

    def get_distance_cm(self) -> float:
        # Random walk, occasionally biased toward a close "obstacle" event.
        step = random.uniform(-15, 15)
        if random.random() < 0.05:
            step -= 60  # simulate something suddenly getting close
        self._distance = max(5.0, min(self.max_distance_cm, self._distance + step))
        return self._distance


class InteractiveMockSensor(BaseUltrasonicSensor):
    """
    Lets you type a distance value into the terminal to manually test alert
    behavior on Mac, instead of random simulated values.
    Type a number (cm) + Enter at any time; it updates the live reading.
    """

    def __init__(self, name: str = "front"):
        self._distance = 200.0
        self.name = name
        self._lock = threading.Lock()
        self._stop = False
        self._thread = threading.Thread(target=self._input_loop, daemon=True)
        self._thread.start()
        logger.info(f"Interactive mock sensor '{name}' active — type a number + Enter to set distance (cm)")

    def _input_loop(self):
        while not self._stop:
            try:
                val = input()
                with self._lock:
                    self._distance = float(val)
            except (ValueError, EOFError):
                continue

    def get_distance_cm(self) -> float:
        with self._lock:
            return self._distance

    def close(self):
        self._stop = True


def create_ultrasonic_sensor(trig_pin: int, echo_pin: int, max_distance_cm: int = 400,
                              name: str = "front", interactive: bool = False) -> BaseUltrasonicSensor:
    """Factory: picks the real sensor on Pi, mock (or interactive mock) elsewhere."""
    if IS_PI:
        try:
            return RealUltrasonicSensor(trig_pin, echo_pin, max_distance_cm)
        except Exception as e:
            logger.warning(f"Failed to init real GPIO sensor ({e}), falling back to mock.")

    if interactive:
        return InteractiveMockSensor(name=name)
    return MockUltrasonicSensor(max_distance_cm=max_distance_cm, name=name)
