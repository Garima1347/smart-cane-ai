"""
Simple shared logger. Logs to console always, and optionally to a file
(configured in config.yaml under `logging:`).
"""

import logging
import sys


def setup_logger(name: str = "smart_cane", level: str = "INFO",
                  log_to_file: bool = False, log_file: str = "smart_cane.log") -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        # Already configured (e.g. imported in multiple modules) — reuse it.
        return logger

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    if log_to_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    return logger
