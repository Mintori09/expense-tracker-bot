"""
Excel storage module for transaction export.
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from config import ensure_data_dir, settings
from database import Transaction, get_transactions

logger = logging.getLogger(__name__)


def export_to_excel(transactions: Optional[list[Transaction]] = None) -> str:
    """Export transactions to Excel file."""
    ensure_data_dir()

    if transactions is None:
        transactions = get_transactions()

    if not transactions:
        return settings.excel_path

    df = pd.DataFrame(
        [
            {
                "Date": tx.date,
                "Merchant": tx.merchant,
                "Amount": tx.amount,
                "Currency": tx.currency,
                "Category": tx.category,
                "Payment Method": tx.payment_method,
                "Description": tx.description,
                "Source": tx.source_type,
                "Confidence": tx.confidence,
                "Needs Review": tx.needs_review,
            }
            for tx in transactions
        ]
    )

    df.to_excel(settings.excel_path, index=False, engine="openpyxl")
    logger.info(f"Exported {len(transactions)} transactions to {settings.excel_path}")

    return settings.excel_path


def export_monthly_summary(year: int, month: int) -> str:
    """Export monthly summary to a separate sheet in Excel."""
    ensure_data_dir()

    from database import get_monthly_summary

    summary = get_monthly_summary(year, month)

    # Create monthly summary DataFrame
    summary_data = [
        {"Category": cat, "Amount": amt} for cat, amt in summary["categories"].items()
    ]

    df = pd.DataFrame(summary_data)
    df.loc[len(df)] = ["TOTAL", summary["total_spent"]]

    # Append to existing Excel or create new
    if Path(settings.excel_path).exists():
        with pd.ExcelWriter(settings.excel_path, mode="a", engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=f"Summary_{year}_{month}", index=False)
    else:
        df.to_excel(
            settings.excel_path, sheet_name=f"Summary_{year}_{month}", index=False
        )

    logger.info(f"Exported monthly summary for {year}-{month}")
    return settings.excel_path
