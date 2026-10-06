"""
Background manager for configured ultrasonic sensors.

Each sensor is polled independently so sensor I/O never blocks the
main vision loop.

The manager stores both the latest distance and metadata about when
that reading was acquired. This allows callers to distinguish a new
physical reading from the same reading being reused.
"""

import logging
import math
import threading
import time
from typing import Any

from src.sensors.ultrasonic import create_ultrasonic_sensor

logger = logging.getLogger("smart_cane")


class SensorManager:
    def __init__(
        self,
        sensor_configs: list,
        poll_interval: float = 0.1,
        interactive: bool = False,
        stale_after_seconds: float = 0.5,
    ):
        """
        sensor_configs:
            List of dictionaries such as:
                {
                    "name": "front",
                    "trig_pin": 23,
                    "echo_pin": 24,
                    "max_distance_cm": 400,
                }

        poll_interval:
            Delay between sensor reads for each sensor.

        interactive:
            Only the first sensor may use interactive stdin input.

        stale_after_seconds:
            Maximum age for a reading to be considered fresh.
        """
        if poll_interval <= 0:
            raise ValueError("poll_interval must be greater than 0")

        if stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be greater than 0")

        self.poll_interval = poll_interval
        self.stale_after_seconds = stale_after_seconds

        self.sensors: dict[str, Any] = {}
        self.latest_readings: dict[str, float | None] = {}

        # Metadata for the latest successful reading.
        self._latest_samples: dict[str, dict | None] = {}

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []

        self._started = False
        self._stopped = False

        configured_names = set()

        for i, cfg in enumerate(sensor_configs):
            name = cfg.get("name")

            if not name:
                raise ValueError("Each sensor configuration must have a name")

            if name in configured_names:
                raise ValueError(f"Duplicate sensor name: {name}")

            configured_names.add(name)

            # Only the first sensor can be interactive because stdin
            # cannot safely be shared by multiple input() threads.
            sensor_interactive = interactive and i == 0

            sensor = create_ultrasonic_sensor(
                trig_pin=cfg["trig_pin"],
                echo_pin=cfg["echo_pin"],
                max_distance_cm=cfg.get("max_distance_cm", 400),
                name=name,
                interactive=sensor_interactive,
            )

            self.sensors[name] = sensor
            self.latest_readings[name] = None
            self._latest_samples[name] = None

    def start(self):
        """Start one polling thread per sensor."""
        if self._started:
            logger.warning("Sensor manager is already started.")
            return

        if self._stopped:
            raise RuntimeError("Cannot restart a stopped SensorManager.")

        self._stop_event.clear()

        for name in self.sensors:
            thread = threading.Thread(
                target=self._poll_loop,
                args=(name,),
                name=f"sensor-{name}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)

        self._started = True
        logger.info(
            "Sensor manager started (%d sensor(s))",
            len(self.sensors),
        )

    def _poll_loop(self, name: str):
        sensor = self.sensors[name]
        sequence = 0

        while not self._stop_event.is_set():
            try:
                distance = sensor.get_distance_cm()

                if not self._is_valid_distance(distance):
                    logger.debug(
                        "Sensor '%s' returned invalid distance: %r",
                        name,
                        distance,
                    )
                else:
                    sequence += 1
                    timestamp = time.monotonic()

                    sample = {
                        "distance_cm": float(distance),
                        "timestamp": timestamp,
                        "sequence": sequence,
                    }

                    with self._lock:
                        self.latest_readings[name] = sample["distance_cm"]
                        self._latest_samples[name] = sample

            except Exception as exc:
                logger.warning(
                    "Sensor '%s' read error: %s",
                    name,
                    exc,
                )

            self._stop_event.wait(self.poll_interval)

    @staticmethod
    def _is_valid_distance(distance) -> bool:
        """Return True only for finite, positive numeric readings."""
        if isinstance(distance, bool):
            return False

        if not isinstance(distance, (int, float)):
            return False

        if not math.isfinite(float(distance)):
            return False

        return float(distance) > 0.0

    def get_latest(self, name: str = "front"):
        """
        Return the latest fresh distance in centimetres.

        Returns None when there is no reading or when the latest reading
        is older than stale_after_seconds.
        """
        sample = self.get_latest_sample(name)

        if sample is None:
            return None

        return sample["distance_cm"]

    def get_latest_sample(self, name: str = "front") -> dict | None:
        """
        Return a copy of the latest fresh sample.

        Sample format:
            {
                "distance_cm": float,
                "timestamp": float,
                "sequence": int,
            }

        timestamp uses time.monotonic(), so it is suitable for measuring
        elapsed time and is not affected by system clock changes.
        """
        with self._lock:
            sample = self._latest_samples.get(name)

            if sample is None:
                return None

            sample_copy = dict(sample)

        age = time.monotonic() - sample_copy["timestamp"]

        if age > self.stale_after_seconds:
            return None

        return sample_copy

    def get_all_latest(self) -> dict:
        """
        Return fresh distance values for all sensors.

        Stale or unavailable readings are returned as None.
        """
        result = {}

        with self._lock:
            samples = {
                name: dict(sample) if sample is not None else None
                for name, sample in self._latest_samples.items()
            }

        now = time.monotonic()

        for name, sample in samples.items():
            if sample is None:
                result[name] = None
                continue

            if now - sample["timestamp"] > self.stale_after_seconds:
                result[name] = None
            else:
                result[name] = sample["distance_cm"]

        return result

    def get_all_latest_samples(self) -> dict:
        """
        Return fresh sample metadata for all sensors.

        The returned dictionary is safe for callers to modify.
        """
        result = {}
        now = time.monotonic()

        with self._lock:
            samples = {
                name: dict(sample) if sample is not None else None
                for name, sample in self._latest_samples.items()
            }

        for name, sample in samples.items():
            if sample is None:
                result[name] = None
                continue

            if now - sample["timestamp"] > self.stale_after_seconds:
                result[name] = None
            else:
                result[name] = sample

        return result

    def stop(self):
        """Stop polling threads and close all sensors."""
        if self._stopped:
            return

        self._stop_event.set()

        for thread in self._threads:
            thread.join(timeout=1.0)

            if thread.is_alive():
                logger.warning(
                    "Sensor thread '%s' did not stop within timeout.",
                    thread.name,
                )

        for sensor in self.sensors.values():
            try:
                sensor.close()
            except Exception as exc:
                logger.warning("Failed to close sensor: %s", exc)

        self._threads.clear()
        self._stopped = True

        logger.info("Sensor manager stopped")