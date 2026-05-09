"""
Database module for storing transactions in SQLite.
"""

import hashlib
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.config import ensure_data_dir, settings

logger = logging.getLogger(__name__)


@dataclass
class Transaction:
    """Transaction data model."""

    date: str
    merchant: str
    amount: float
    currency: str
    category: str
    payment_method: str = "Unknown"
    description: str = ""
    source_type: str = "text"
    confidence: float = 1.0
    needs_review: bool = False
    id: Optional[int] = None
    source_hash: Optional[str] = None
    user_id: Optional[int] = None

    def compute_hash(self, source_text: str = "") -> str:
        """Compute unique hash for deduplication."""
        content = f"{self.date}|{self.merchant}|{self.amount}|{source_text}"
        return hashlib.md5(content.encode()).hexdigest()


def get_connection() -> sqlite3.Connection:
    """Get database connection."""
    ensure_data_dir()
    return sqlite3.connect(settings.sqlite_path)


def init_schema() -> None:
    """Initialize database schema - creates tables if not exists."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            merchant TEXT,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            category TEXT NOT NULL,
            payment_method TEXT,
            description TEXT,
            source_type TEXT,
            confidence REAL,
            needs_review INTEGER,
            source_hash TEXT UNIQUE,
            user_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS merchant_categories (
            merchant TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    logger.info("Database schema initialized")


@contextmanager
def get_db_cursor():
    """Context manager for database operations."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def add_transaction(tx: Transaction, source_text: str = "") -> int | None:
    """Add a new transaction to the database."""
    if tx.source_hash is None:
        tx.source_hash = tx.compute_hash(source_text)

    with get_db_cursor() as cursor:
        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO transactions 
                (date, merchant, amount, currency, category, payment_method, description, source_type, confidence, needs_review, source_hash, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    tx.date,
                    tx.merchant,
                    tx.amount,
                    tx.currency,
                    tx.category,
                    tx.payment_method,
                    tx.description,
                    tx.source_type,
                    tx.confidence,
                    tx.needs_review,
                    tx.source_hash,
                    tx.user_id,
                ),
            )
            tx_id = cursor.lastrowid
            if tx_id:
                logger.info(
                    f"Added transaction: {tx.merchant} - {tx.amount} {tx.currency}"
                )
            else:
                logger.info(f"Duplicate skipped: {tx.merchant} - {tx.amount}")
            return tx_id
        except sqlite3.IntegrityError:
            logger.info(f"Duplicate transaction skipped: {tx.merchant} - {tx.amount}")
            return None


def get_monthly_summary(year: int, month: int) -> dict:
    """Get monthly spending summary."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT category, SUM(amount) as total
            FROM transactions
            WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?
            GROUP BY category
            ORDER BY total DESC
        """,
            (str(year), f"{month:02d}"),
        )

        results = cursor.fetchall()

    total_spent = sum(row[1] for row in results)

    return {
        "year": year,
        "month": month,
        "total_spent": total_spent,
        "categories": {row[0]: row[1] for row in results},
    }


def normalize_merchant(merchant: str) -> str:
    """Normalize merchant name for better matching."""
    if not merchant:
        return ""
    # Remove special characters, lowercase
    import re

    normalized = re.sub(r"[^\w\s]", "", merchant.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def find_duplicates(
    merchant: str, amount: float, date: str, tolerance_days: int = 1
) -> list[Transaction]:
    """Find potential duplicate transactions."""
    # Dynamic tolerance based on amount
    tolerance = max(1000, amount * 0.02)
    normalized = normalize_merchant(merchant)

    with get_db_cursor() as cursor:
        # Use BETWEEN for date range and normalized merchant
        cursor.execute(
            """
            SELECT * FROM transactions
            WHERE date BETWEEN ? AND ?
            AND ABS(amount - ?) < ?
            AND merchant LIKE ?
        """,
            (
                f"{date} 00:00:00",
                f"{date} 23:59:59",
                amount,
                tolerance,
                f"%{normalized}%",
            ),
        )

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


def get_transactions(limit: int = 100) -> list[Transaction]:
    """Get recent transactions."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM transactions
            ORDER BY date DESC, created_at DESC
            LIMIT ?
        """,
            (limit,),
        )

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


def get_needs_review_transactions() -> list[Transaction]:
    """Get transactions that need review."""
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM transactions
            WHERE needs_review = 1
            ORDER BY created_at DESC
        """)

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


def learn_category(merchant: str, category: str) -> None:
    """Store merchant-category mapping for future learning."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            INSERT OR REPLACE INTO merchant_categories (merchant, category, updated_at)
            VALUES (?, ?, ?)
        """,
            (merchant, category, datetime.now().isoformat()),
        )
    logger.info(f"Learned: {merchant} -> {category}")


def get_learned_category(merchant: str) -> Optional[str]:
    """Get learned category for a merchant."""
    normalized = normalize_merchant(merchant)
    with get_db_cursor() as cursor:
        cursor.execute(
            "SELECT category FROM merchant_categories WHERE merchant LIKE ?",
            (f"%{normalized}%",),
        )
        row = cursor.fetchone()
    return row[0] if row else None


def get_transaction(tx_id: int) -> Optional[Transaction]:
    """Get a single transaction by ID."""
    with get_db_cursor() as cursor:
        cursor.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,))
        row = cursor.fetchone()

    if not row:
        return None

    return Transaction(
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


def get_today_transactions() -> list[Transaction]:
    """Get today's transactions."""
    today = datetime.now().strftime("%Y-%m-%d")
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            SELECT * FROM transactions
            WHERE date = ?
            ORDER BY created_at DESC
        """,
            (today,),
        )
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


def delete_transaction(tx_id: int) -> bool:
    """Delete a transaction by ID."""
    with get_db_cursor() as cursor:
        cursor.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        return cursor.rowcount > 0


def update_transaction(tx_id: int, tx: Transaction) -> bool:
    """Update an existing transaction."""
    with get_db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE transactions
            SET date=?, merchant=?, amount=?, currency=?, category=?, 
                payment_method=?, description=?
            WHERE id=?
        """,
            (
                tx.date,
                tx.merchant,
                tx.amount,
                tx.currency,
                tx.category,
                tx.payment_method,
                tx.description,
                tx_id,
            ),
        )
        return cursor.rowcount > 0