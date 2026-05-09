"""Shared utilities for Telegram Bot System."""

from app.shared.constants import DEFAULT_CURRENCY
from app.shared.exceptions import (
    ExtractionError,
    OCRFailedError,
    InvalidTransactionError,
    handle_error,
)

__all__ = [
    "DEFAULT_CURRENCY",
    "ExtractionError",
    "OCRFailedError",
    "InvalidTransactionError",
    "handle_error",
]