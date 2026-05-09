"""Constants for Finance module."""

from pathlib import Path

# Data paths
FINANCE_DATA_DIR = Path("data/finance")
EXPENSE_DB_PATH = FINANCE_DATA_DIR / "expenses.db"
EXPENSE_EXCEL_FILE = FINANCE_DATA_DIR / "expenses.xlsx"

# Default currency
DEFAULT_CURRENCY = "VND"

# Category mappings
DEFAULT_CATEGORIES = [
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

__all__ = [
    "FINANCE_DATA_DIR",
    "EXPENSE_DB_PATH",
    "EXPENSE_EXCEL_FILE",
    "DEFAULT_CURRENCY",
    "DEFAULT_CATEGORIES",
]
