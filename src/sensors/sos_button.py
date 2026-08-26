"""
Emergency SOS push button. Hold for `hold_seconds` to trigger an emergency
alert — deliberately requires a hold (not a tap) so it isn't triggered
accidentally by the cane bumping into something.

This is intentionally kept simple (voice + haptic alert repeating), but the
`on_trigger` callback is the natural place to later hook in:
  - a GSM/SIM module to send an SMS with GPS coordinates to a caregiver
  - a WiFi call to a family member's phone via a notification service
  - flashing an LED strip for sighted bystanders nearby

Those need extra hardware (GSM module, GPS module) not assumed to be part
of the base build, so they're left as a documented extension point rather
than built in — see README "Extending with SOS notifications".
"""

import logging
import threading
import time

from src.utils.platform_utils import IS_PI

logger = logging.getLogger("smart_cane")


class BaseSOSButton:
    def start(self, on_trigger):
        pass

    def stop(self):
        pass


class RealSOSButton(BaseSOSButton):
    def __init__(self, pin: int, hold_seconds: float = 2.0):
        from gpiozero import Button
        from gpiozero.pins.lgpio import LGPIOFactory

        self.button = Button(pin, pin_factory=LGPIOFactory(), hold_time=hold_seconds)
        logger.info(f"SOS button initialized on GPIO{pin} (hold {hold_seconds}s to trigger)")

    def start(self, on_trigger):
        self.button.when_held = lambda: on_trigger()

    def stop(self):
        self.button.close()


class KeyboardSOSButton(BaseSOSButton):
    """
    Mac dev substitute: press Enter in the terminal to simulate holding the
    SOS button (no physical button attached during development).
    """

    def __init__(self):
        self._stop = False
        self._thread = None
        logger.info("Keyboard SOS substitute active — press Enter + 's' then Enter to simulate SOS press")

    def start(self, on_trigger):
        def loop():
            while not self._stop:
                try:
                    line = input()
                except EOFError:
                    return
                if line.strip().lower() == "s":
                    on_trigger()
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True


def create_sos_button(pin: int = None, hold_seconds: float = 2.0) -> BaseSOSButton:
    if IS_PI and pin is not None:
        try:
            return RealSOSButton(pin, hold_seconds)
        except Exception as e:
            logger.warning(f"SOS button init failed ({e}), continuing without physical SOS button.")
    return KeyboardSOSButton()
