"""Finance module storage - Excel export operations."""

import logging
from datetime import datetime, timedelta

from app.config import ensure_data_dir, settings
from app.core.database import Transaction, get_db_cursor, get_transactions

logger = logging.getLogger(__name__)


def get_transactions_last_n_days(n: int, user_id: int = None) -> list[Transaction]:
    """Get transactions from the last N days."""
    now = datetime.now()
    start = now - timedelta(days=n - 1)
    end = now
    
    query = "SELECT * FROM transactions WHERE date BETWEEN ? AND ?"
    params = [start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")]
    
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
    
    query += " ORDER BY date DESC"
    
    with get_db_cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    
    return [
        Transaction(
            id=row[0],
            date=row[1],
            merchant=row[2],
            amount=row[3],
            currency=row[4],
            category=row[5],
            payment_method=row[6],
            description=row[7],
            source_type=row[8],
            confidence=row[9],
            needs_review=bool(row[10]),
            source_hash=row[11] if len(row) > 11 else None,
            user_id=row[12] if len(row) > 12 else None,
        )
        for row in rows
    ]


def export_to_excel(transactions: list[Transaction] = None) -> str:
    """Export transactions to Excel file."""
    ensure_data_dir()
    import pandas as pd

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


def get_transactions_by_period(
    period: str, year: int = None, month: int = None, user_id: int = None
) -> list[Transaction]:
    """Get transactions filtered by period (today, week, month, year) and optionally by user_id."""
    now = datetime.now()
    year = year or now.year
    month = month or now.month

    if period == "today":
        date = now.strftime("%Y-%m-%d")
        query = "SELECT * FROM transactions WHERE date = ?"
        params = [date]
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        query += " ORDER BY date DESC"
        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
    elif period == "week":
        # Current week (Monday to Sunday)
        start = now - timedelta(days=now.weekday())
        end = start + timedelta(days=6)
        query = "SELECT * FROM transactions WHERE date BETWEEN ? AND ?"
        params = [start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")]
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        query += " ORDER BY date DESC"
        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
    elif period == "month":
        query = """SELECT * FROM transactions 
                   WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?"""
        params = [str(year), f"{month:02d}"]
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        query += " ORDER BY date DESC"
        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
    elif period == "year":
        query = "SELECT * FROM transactions WHERE strftime('%Y', date) = ?"
        params = [str(year)]
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        query += " ORDER BY date DESC"
        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
    else:
        return []

    return [
        Transaction(
            id=row[0],
            date=row[1],
            merchant=row[2],
            amount=row[3],
            currency=row[4],
            category=row[5],
            payment_method=row[6],
            description=row[7],
            source_type=row[8],
            confidence=row[9],
            needs_review=bool(row[10]),
            source_hash=row[11] if len(row) > 11 else None,
            user_id=row[12] if len(row) > 12 else None,
        )
        for row in rows
    ]


def export_period_to_excel(
    period: str, year: int = None, month: int = None, user_id: int = None
) -> tuple[str, int]:
    """Export transactions for a specific period to Excel.

    Returns: (file_path, transaction_count)
    """
    ensure_data_dir()
    import pandas as pd

    transactions = get_transactions_by_period(period, year, month, user_id)

    file_name = settings.excel_path.replace(".xlsx", f"_{period}.xlsx")

    if not transactions:
        # Create empty file with headers
        df = pd.DataFrame(
            columns=[
                "Date",
                "Merchant",
                "Amount",
                "Currency",
                "Category",
                "Payment Method",
                "Description",
                "Source",
                "Confidence",
                "Needs Review",
            ]
        )
        df.to_excel(file_name, index=False, engine="openpyxl")
        return file_name, 0

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

    df.to_excel(file_name, index=False, engine="openpyxl")
    logger.info(f"Exported {len(transactions)} transactions to {file_name}")

    return file_name, len(transactions)


def export_monthly_summary(year: int, month: int) -> str:
    """Export monthly summary to a separate sheet in Excel."""
    ensure_data_dir()
    import pandas as pd

    from app.core.database import get_monthly_summary

    summary = get_monthly_summary(year, month)

    # Create monthly summary DataFrame
    summary_data = [
        {"Category": cat, "Amount": amt} for cat, amt in summary["categories"].items()
    ]

    df = pd.DataFrame(summary_data)
    df.loc[len(df)] = ["TOTAL", summary["total_spent"]]

    # Append to existing Excel or create new
    from pathlib import Path

    if Path(settings.excel_path).exists():
        with pd.ExcelWriter(settings.excel_path, mode="a", engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=f"Summary_{year}_{month}", index=False)
    else:
        df.to_excel(
            settings.excel_path, sheet_name=f"Summary_{year}_{month}", index=False
        )

    logger.info(f"Exported monthly summary for {year}-{month}")
    return settings.excel_path


__all__ = ["export_to_excel", "export_period_to_excel", "export_monthly_summary"]

