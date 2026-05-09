"""Bot dispatcher - creates and configures the Telegram application."""

import logging

from telegram import Update
from telegram.ext import Application

from app.config import settings
from app.modules.finance.handlers import register_finance_handlers

logger = logging.getLogger(__name__)


def create_application() -> Application:
    """Create and configure the Telegram application."""
    application = Application.builder().token(settings.telegram_bot_token).build()

    # Register module handlers
    register_finance_handlers(application)

    return application


def run_bot() -> None:
    """Start the bot polling."""
    application = create_application()
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

