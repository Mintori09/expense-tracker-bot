"""
Main entry point for Telegram Bot System.
Bootstraps the application.
"""

from app.bot.dispatcher import run_bot
from app.core.database import init_schema
from app.core.logging import setup_logging

# Setup logging
setup_logging()


def main() -> None:
    """Start the bot."""
    # Initialize database
    init_schema()
    
    # Run the bot
    run_bot()


if __name__ == "__main__":
    main()