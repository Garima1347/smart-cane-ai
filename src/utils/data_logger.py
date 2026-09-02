"""
Logs every spoken alert to a CSV file with a timestamp, so a caregiver or
the user themselves can later review what hazards came up on a given walk
(e.g. "lots of pothole alerts on the route to the market — maybe avoid it").

Kept intentionally simple (local CSV, no cloud dependency) so it works
fully offline, consistent with the rest of the system's offline-first design.
"""

import csv
import logging
import os
import threading
from datetime import datetime

logger = logging.getLogger("smart_cane")


class DataLogger:
    def __init__(self, filepath: str = "obstacle_log.csv"):
        self.filepath = filepath
        self._lock = threading.Lock()
        self._ensure_header()

    def _ensure_header(self):
        file_exists = os.path.isfile(self.filepath)
        if not file_exists:
            with open(self.filepath, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "alert_key", "phrase", "urgent", "distance_m"])

    def log_alert(self, alert_key: str, phrase: str, urgent: bool, distance_m: float = None):
        with self._lock:
            with open(self.filepath, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(timespec="seconds"),
                    alert_key,
                    phrase,
                    urgent,
                    f"{distance_m:.2f}" if distance_m is not None else "",
                ])

    def session_summary(self) -> dict:
        """Quick counts, handy to speak/print at shutdown ('12 alerts this walk, 2 urgent')."""
        total, urgent_count = 0, 0
        if not os.path.isfile(self.filepath):
            return {"total": 0, "urgent": 0}
        with open(self.filepath, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += 1
                if row["urgent"] == "True":
                    urgent_count += 1
        return {"total": total, "urgent": urgent_count}
