"""
Detects which platform we're running on (macOS dev machine vs Raspberry Pi)
so the rest of the codebase can pick the right hardware backend without
any manual flags.
"""

import platform
import os


def is_raspberry_pi() -> bool:
    """Return True if running on a Raspberry Pi (any model)."""
    # Most reliable check: /proc/cpuinfo contains "Raspberry Pi" or "BCM" on Pi OS.
    if platform.system() != "Linux":
        return False
    try:
        with open("/proc/cpuinfo", "r") as f:
            cpuinfo = f.read()
        return "Raspberry Pi" in cpuinfo or "BCM" in cpuinfo
    except FileNotFoundError:
        return False


def is_macos() -> bool:
    return platform.system() == "Darwin"


def get_platform_name() -> str:
    if is_raspberry_pi():
        return "raspberry_pi"
    elif is_macos():
        return "macos"
    else:
        return "linux_generic"


def has_picamera2() -> bool:
    """Check if the picamera2 library (Pi Camera Module) is importable."""
    try:
        import picamera2  # noqa: F401
        return True
    except ImportError:
        return False


def has_gpio_support() -> bool:
    """Check if gpiozero (with lgpio backend) is available — Pi 5 compatible."""
    try:
        import gpiozero  # noqa: F401
        return True
    except ImportError:
        return False


PLATFORM = get_platform_name()
IS_PI = PLATFORM == "raspberry_pi"
IS_MAC = PLATFORM == "macos"
