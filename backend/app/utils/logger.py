"""Logging configuration for structured JSON logging."""

import logging
import sys
from pythonjsonlogger import jsonlogger


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Get a configured JSON logger.

    Args:
        name: Logger name (typically __name__)
        level: Log level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Configured logger instance with JSON formatting
    """
    logger = logging.getLogger(name)

    # Only configure if handlers don't exist (avoid duplicates)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = jsonlogger.JsonFormatter()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)

    return logger