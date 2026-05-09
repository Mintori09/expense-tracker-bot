"""Shared exceptions and error handling."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Raised when LLM extraction fails."""

    pass


class OCRFailedError(Exception):
    """Raised when OCR processing fails."""

    pass


class InvalidTransactionError(Exception):
    """Raised when transaction data is invalid."""

    pass


def handle_error(error: Exception, context: Optional[str] = None) -> str:
    """Generate user-friendly error message."""
    logger.error(f"{context}: {error}" if context else str(error))

    if isinstance(error, ExtractionError):
        return "*Sorry, I couldn't extract the transaction details. Please try rephrasing or send a clearer receipt.*"
    elif isinstance(error, OCRFailedError):
        return "*Failed to process the image. Please make sure the text is clear and try again.*"
    elif isinstance(error, InvalidTransactionError):
        return f"*Invalid transaction: {str(error)}. Please check and try again.*"
    else:
        return "*An unexpected error occurred. Please try again later.*"
