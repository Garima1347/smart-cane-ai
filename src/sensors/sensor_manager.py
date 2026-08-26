"""
Runs one background polling thread per configured ultrasonic sensor, so
distance readings are always fresh and never block the main/vision loop.
Exposes the latest reading per sensor via get_latest().
"""

import logging
import threading
import time

from src.sensors.ultrasonic import create_ultrasonic_sensor

logger = logging.getLogger("smart_cane")


class SensorManager:
    def __init__(self, sensor_configs: list, poll_interval: float = 0.1, interactive: bool = False):
        """
        sensor_configs: list of dicts like
            {"name": "front", "trig_pin": 23, "echo_pin": 24, "max_distance_cm": 400}
        """
        self.poll_interval = poll_interval
        self.sensors = {}
        self.latest_readings = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._threads = []

        for i, cfg in enumerate(sensor_configs):
            # Only the FIRST sensor can be interactive (stdin can't be shared
            # across multiple input() threads) — other sensors fall back to
            # the random-walk mock even when --interactive-sensor is passed.
            sensor_interactive = interactive and i == 0
            sensor = create_ultrasonic_sensor(
                trig_pin=cfg["trig_pin"],
                echo_pin=cfg["echo_pin"],
                max_distance_cm=cfg.get("max_distance_cm", 400),
                name=cfg["name"],
                interactive=sensor_interactive,
            )
            self.sensors[cfg["name"]] = sensor
            self.latest_readings[cfg["name"]] = None

    def start(self):
        for name in self.sensors:
            t = threading.Thread(target=self._poll_loop, args=(name,), daemon=True)
            t.start()
            self._threads.append(t)
        logger.info(f"Sensor manager started ({len(self.sensors)} sensor(s))")

    def _poll_loop(self, name: str):
        sensor = self.sensors[name]
        while not self._stop_event.is_set():
            try:
                distance = sensor.get_distance_cm()
                with self._lock:
                    self.latest_readings[name] = distance
            except Exception as e:
                logger.debug(f"Sensor '{name}' read error: {e}")
            time.sleep(self.poll_interval)

    def get_latest(self, name: str = "front"):
        with self._lock:
            return self.latest_readings.get(name)

    def get_all_latest(self) -> dict:
        with self._lock:
            return dict(self.latest_readings)

    def stop(self):
        self._stop_event.set()
        for t in self._threads:
            t.join(timeout=1.0)
        for sensor in self.sensors.values():
            sensor.close()
        logger.info("Sensor manager stopped")
