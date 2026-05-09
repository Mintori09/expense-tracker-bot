"""Finance module data models."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Expense:
    """Expense data model."""

    date: str
    merchant: str
    amount: float
    currency: str = "VND"
    category: str = "Other"
    payment_method: str = "Chuyển khoản"
    description: str = ""
    source_type: str = "text"
    confidence: float = 1.0
    needs_review: bool = False
    id: Optional[int] = None

    def is_valid(self) -> bool:
        """Check if expense has valid data."""
        return self.amount > 0 and self.date


@dataclass
class FinanceSummary:
    """Summary of financial data."""

    total_spent: float = 0
    categories: dict = None

    def __post_init__(self):
        if self.categories is None:
            self.categories = {}


__all__ = ["Expense", "FinanceSummary"]
