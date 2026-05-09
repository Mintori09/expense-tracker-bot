#!/usr/bin/env python3
"""Test script for transaction extraction and database."""

from database import (
    Transaction,
    add_transaction,
    get_monthly_summary,
    get_transactions,
    init_db,
)
from extractor import (
    extract_simple_fallback,
    extract_transaction,
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


def test_database():
    """Test database operations."""
    print("\n=== Database Tests ===")

    # Initialize DB
    init_db()
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


async def test_llm_extraction():
    """Test LLM extraction (requires running Ollama)."""
    print("\n=== LLM Extraction Tests ===")
    for text in test_samples[:3]:  # Test first 3
        try:
            result = await extract_transaction(text)
            print(f"✓ '{text}'")
            print(
                f"   -> Amount: {result.amount}, Merchant: {result.merchant}, Category: {result.category}"
            )
        except Exception as e:
            print(f"✗ '{text}' - Error: {e}")


if __name__ == "__main__":
    test_parse_amount()
    test_fallback_extraction()
    test_database()

    # Uncomment to test LLM extraction (requires Ollama running)
    # asyncio.run(test_llm_extraction())

    print("\n=== All tests completed ===")
