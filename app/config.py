"""
Configuration module for Finance Automation Bot.
"""

from pathlib import Path
from typing import Any

from openai import AsyncOpenAI
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Telegram Bot
    telegram_bot_token: str

    # LLM Provider: "ollama" or "google"
    llm_provider: str = "ollama"

    # LLM Configuration (OpenAI-compatible)
    llm_api_key: str = "ollama"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "gemma3:4b-it-qat"

    # Ollama Configuration
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b-it-qat"

    # Google AI Configuration
    google_api_key: str = ""
    google_model: str = "gemini-1.5-flash"

    # Database
    sqlite_path: str = "data/finance/expenses.db"

    # Excel Storage
    excel_path: str = "data/finance/expenses.xlsx"

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


settings = Settings()


def ensure_data_dir() -> None:
    """Ensure data directories exist."""
    Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    Path(settings.excel_path).parent.mkdir(parents=True, exist_ok=True)


def get_llm_client() -> AsyncOpenAI:
    """Get the appropriate LLM client based on provider."""
    if settings.llm_provider == "google":
        return AsyncOpenAI(
            api_key=settings.google_api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )

    return AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )


def mask_secret(value: Any) -> Any:
    """Mask sensitive values before printing."""
    if not isinstance(value, str) or not value:
        return value

    if len(value) <= 10:
        return "***"

    return f"{value[:6]}...{value[-4:]}"


def print_config() -> None:
    """Print current application config, hiding secrets."""
    data = settings.model_dump()

    secret_keys = {
        "telegram_bot_token",
        "llm_api_key",
        "google_api_key",
    }

    print("Current configuration:")
    print("-" * 30)

    for key, value in data.items():
        if key in secret_keys:
            value = mask_secret(value)

        print(f"{key}: {value}")
