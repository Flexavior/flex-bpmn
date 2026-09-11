"""Logging helper shared across the application."""

from __future__ import annotations

import logging
import sys

from app.config import LOG_LEVEL


def get_logger(name: str = "fxv-bpmn") -> logging.Logger:
    """Return a configured logger (JSON-friendly, single handler)."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        _level = getattr(logging, str(LOG_LEVEL).upper(), logging.INFO)
        logger.setLevel(_level)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            )
        )
        logger.addHandler(handler)
        logger.propagate = False
    return logger