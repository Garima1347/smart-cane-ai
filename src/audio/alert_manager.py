"""
Decides WHEN to actually speak/vibrate an alert (vs. suppress it because we
just said something similar). Without this, the system would try to speak
on every single frame/sensor reading, producing a garbled, unusable stream
of overlapping speech.

Rules:
  - Each distinct alert "key" (e.g. "danger_front", "person_center") has its
    own cooldown timer.
  - Danger-level alerts get a shorter cooldown (repeat sooner) than routine
    warnings, since they're more time-critical.
  - A new *danger* alert can interrupt/clear a queued lower-priority phrase.
  - Cooldowns shrink automatically when the user is closing in on an
    obstacle quickly (see ClosingSpeedTracker in obstacle_logic.py) — you
    get faster-repeating warnings exactly when you need them most.
  - Every triggered alert also fires the matching haptic pattern, and is
    logged to the CSV data logger if one is attached (for later review).
"""

import logging
import time

from src.audio.voice_alert import VoiceEngine

logger = logging.getLogger("smart_cane")


class AlertManager:
    def __init__(self, voice_engine: VoiceEngine, cooldown_seconds: float = 2.5,
                 urgent_cooldown_seconds: float = 1.0, haptic_engine=None, data_logger=None):
        self.voice_engine = voice_engine
        self.cooldown_seconds = cooldown_seconds
        self.urgent_cooldown_seconds = urgent_cooldown_seconds
        self.haptic_engine = haptic_engine
        self.data_logger = data_logger
        self._last_spoken = {}  # alert_key -> timestamp
        self._active_haptic = "off"

    def trigger(self, alert_key: str, phrase: str, urgent: bool = False,
                haptic: str = "off", distance_m: float = None, speed_multiplier: float = 1.0):
        """
        Attempt to speak `phrase`, identified by `alert_key` for cooldown
        tracking. `speed_multiplier` < 1.0 shortens the cooldown (used when
        the user is closing in on the obstacle fast).
        Returns True if it was actually spoken, False if suppressed.
        """
        now = time.time()
        base_cooldown = self.urgent_cooldown_seconds if urgent else self.cooldown_seconds
        cooldown = base_cooldown * speed_multiplier
        last_time = self._last_spoken.get(alert_key, 0)

        if now - last_time < cooldown:
            return False  # still on cooldown, suppress

        if urgent:
            # Urgent alerts take priority — clear anything queued that isn't spoken yet.
            self.voice_engine.clear_queue()

        self.voice_engine.speak(phrase)
        self._last_spoken[alert_key] = now

        if self.haptic_engine:
            self.haptic_engine.pulse_pattern(haptic)
            self._active_haptic = haptic

        if self.data_logger:
            self.data_logger.log_alert(alert_key, phrase, urgent, distance_m)

        logger.info(f"ALERT{' [URGENT]' if urgent else ''}: {phrase}")
        return True

    def clear_haptic_if_idle(self, active_keys: set):
        """
        Call once per cycle with the set of alert_keys that fired THIS
        cycle. If nothing fired, stop any lingering vibration pattern.
        """
        if not active_keys and self._active_haptic != "off" and self.haptic_engine:
            self.haptic_engine.pulse_pattern("off")
            self._active_haptic = "off"
