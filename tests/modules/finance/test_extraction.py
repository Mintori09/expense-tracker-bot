"""Test script for transaction extraction and database."""

import os
import tempfile

import pytest

from app.modules.finance.extractor import (
    extract_simple_fallback,
    parse_vietnamese_amount,
)

# Test samples
test_samples = [
    "Ăn trưa 85k ở Phở Thìn",
    "cà phê 55k tại The Coffee House",
    "GrabBike 45k",
    "mua bánh mì 20k",
    "2.5tr internet VNPT",
    "Netflix 260k/tháng",
    "Ăn tối 120,000 VND tại nhà hàng",
]


def test_parse_amount():
    """Test Vietnamese amount parsing."""
    test_cases = [
        ("85k", 85000),
        ("85.5k", 85500),
        ("2tr", 2000000),
        ("2.5tr", 2500000),
        ("100,000", 100000),
    ]

    print("=== Amount Parsing Tests ===")
    for text, expected in test_cases:
        result = parse_vietnamese_amount(text)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{text}' -> {result} (expected {expected})")


def test_fallback_extraction():
    """Test fallback extraction without LLM."""
    print("\n=== Fallback Extraction Tests ===")
    for text in test_samples:
        result = extract_simple_fallback(text)
        if result:
            print(f"✓ '{text}'")
            print(
                f"   -> Amount: {result.amount}, Merchant: {result.merchant}, Category: {result.category}"
            )
        else:
            print(f"✗ '{text}' - No match")


# Use temp directory for test database
_test_db_fd, _test_db_path = tempfile.mkstemp(suffix=".db")
os.close(_test_db_fd)


def test_database():
    """Test database operations."""
    from app.config import settings

    # Override database path for tests
    original_path = settings.sqlite_path
    settings.sqlite_path = _test_db_path

    from app.core.database import (
        Transaction,
        add_transaction,
        get_monthly_summary,
        get_transactions,
        init_schema,
    )

    print("\n=== Database Tests ===")

    # Initialize DB
    init_schema()
    print("✓ Database initialized")

    # Add test transaction
    tx = Transaction(
        date="2025-01-15",
        merchant="Test Store",
        amount=50000,
        currency="VND",
        category="Shopping",
        payment_method="Cash",
        description="Test purchase",
        source_type="text",
        confidence=1.0,
        needs_review=False,
    )

    tx_id = add_transaction(tx)
    print(f"✓ Added transaction with ID: {tx_id}")

    # Get all transactions
    transactions = get_transactions(10)
    print(f"✓ Retrieved {len(transactions)} transactions")

    # Get monthly summary
    summary = get_monthly_summary(2025, 1)
    print(f"✓ Monthly summary: Total {summary['total_spent']} VND")

    # Cleanup
    settings.sqlite_path = original_path
    try:
        os.unlink(_test_db_path)
    except Exception:
        pass


# Cleanup on exit
import atexit


def _cleanup_test_db():
    try:
        os.unlink(_test_db_path)
    except Exception:
        pass


atexit.register(_cleanup_test_db)