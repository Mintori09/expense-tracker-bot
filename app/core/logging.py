"""Logging configuration for the application."""

import logging
import sys

from app.config import settings


def setup_logging():
    """Configure application logging."""
    # Ensure logs directory exists
    import os

    os.makedirs("logs", exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("logs/bot.log", encoding="utf-8"),
        ],
    )
    return logging.getLogger(__name__)

