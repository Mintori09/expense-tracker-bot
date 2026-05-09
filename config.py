"""
Configuration module for Finance Automation Bot.
"""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Telegram Bot
    telegram_bot_token: str

    # LLM Configuration (OpenAI-compatible)
    llm_api_key: str = "ollama"  # Default to ollama
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "gemma3:4b-it-qat"

    # Ollama Configuration
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b-it-qat"

    # Database
    sqlite_path: str = "data/expenses.db"

    # Excel Storage
    excel_path: str = "data/expenses.xlsx"

    # Logging
    log_level: str = "INFO"

    # Category mappings
    default_categories: list[str] = [
        "Food",
        "Coffee",
        "Groceries",
        "Transport",
        "Rent",
        "Utilities",
        "Shopping",
        "Health",
        "Education",
        "Entertainment",
        "Travel",
        "Subscription",
        "Income",
        "Other",
    ]

    # Merchant to category learning
    merchant_category_map: dict[str, str] = {
        "Highlands Coffee": "Coffee",
        "The Coffee House": "Coffee",
        "Phở": "Food",
        "GrabBike": "Transport",
        "GrabFood": "Food",
        "Circle K": "Groceries",
        "Netflix": "Subscription",
    }

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


def ensure_data_dir():
    """Ensure data directory exists."""
    Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    Path(settings.excel_path).parent.mkdir(parents=True, exist_ok=True)
