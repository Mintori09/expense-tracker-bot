"""Bot dispatcher - creates and configures the Telegram application."""

import logging

from telegram import BotCommand, Update
from telegram.ext import Application

from app.config import settings
from app.modules.finance.handlers import register_finance_handlers

logger = logging.getLogger(__name__)

# Bot commands for auto-complete
BOT_COMMANDS = [
    BotCommand("start", "Start the bot"),
    BotCommand("help", "Show help"),
    BotCommand("month", "Monthly summary"),
    BotCommand("today", "Today's expenses"),
    BotCommand("current", "Current balance"),
    BotCommand("setbalance", "Set initial balance"),
    BotCommand("export", "Export to Excel"),
    BotCommand("review", "Review transactions"),
    BotCommand("edit", "Edit transaction"),
    BotCommand("remove", "Remove transaction"),
    BotCommand("getid", "Get chat ID"),
    BotCommand("language", "Change language"),
]


def create_application() -> Application:
    """Create and configure the Telegram application."""
    application = Application.builder().token(settings.telegram_bot_token).build()

    # Register module handlers
    register_finance_handlers(application)

    return application


async def set_bot_commands(app: Application) -> None:
    """Set bot commands on startup."""
    await app.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Bot commands set")


def run_bot() -> None:
    """Start the bot polling."""
    application = create_application()

    # Set post_init callback directly
    application.post_init = set_bot_commands

    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
