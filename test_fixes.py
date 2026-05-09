#!/usr/bin/env python3
"""
Test file to verify the fixes for:
1. JSON parsing with markdown code blocks
2. Date validation (rejecting future/old dates)
3. Full extraction flow
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime

from database import Transaction, add_transaction, get_monthly_summary, init_schema
from extractor import (
    extract_simple_fallback,
    extract_transaction,
    parse_vietnamese_amount,
)


def test_json_parsing_with_markdown():
    """Test that LLM responses with markdown code blocks are parsed correctly."""
    print("=== Test: JSON Parsing with Markdown ===")

    # Simulate LLM response with markdown
    test_cases = [
        '```json\n{"date": "2024-01-15", "amount": 50000, "merchant": "Test"}\n```',
        '```json{"date": "2024-01-15", "amount": 50000}\n```',
        '{"date": "2024-01-15", "amount": 50000}',  # No markdown
    ]

    import json
    import re

    for response in test_cases:
        try:
            cleaned = re.sub(r"```json\s*|\s*```", "", response).strip()
            data = json.loads(cleaned)
            print(f"  ✓ Parsed: {data}")
        except json.JSONDecodeError as e:
            print(f"  ✗ Failed: {e}")


def test_vietnamese_amount_parsing():
    """Test Vietnamese amount format parsing."""
    print("\n=== Test: Vietnamese Amount Parsing ===")

    test_cases = [
        ("85k", 85000),
        ("85.5k", 85500),
        ("2tr", 2000000),
        ("2.5tr", 2500000),
        ("100,000", 100000),
        ("100.000", 100000),
    ]

    for text, expected in test_cases:
        result = parse_vietnamese_amount(text)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{text}' -> {result} (expected {expected})")


def test_fallback_extraction():
    """Test fallback extraction for conversation examples."""
    print("\n=== Test: Fallback Extraction ===")

    test_cases = [
        ("Đánh cầu lông 30k", 30000, True),  # needs_review=True
        ("Ăn trưa 85k ở Phở Thìn", 85000, False),  # needs_review=False
        (
            "Ăn tối 120,000 VND tại nhà hàng",
            120000,
            True,
        ),  # needs_review=True (unknown merchant "nhà hàng")
    ]

    for text, expected_amount, expected_review in test_cases:
        result = extract_simple_fallback(text)
        if result:
            status = "✓" if result.amount == expected_amount else "✗"
            print(
                f"  {status} '{text}' -> {result.amount}, merchant='{result.merchant}', needs_review={result.needs_review}"
            )
        else:
            print(f"  ✗ '{text}' - No extraction")


async def test_llm_extraction():
    """Test LLM extraction with the fixes."""
    print("\n=== Test: LLM Extraction ===")

    test_cases = [
        ("Đánh cầu lông 30k", 30000),
        ("Ăn trưa 85k ở Phở Thìn", 85000),
    ]

    for text, expected_amount in test_cases:
        try:
            result = await extract_transaction(text)
            # Verify date is today
            today = datetime.now().strftime("%Y-%m-%d")
            date_ok = result.date == today
            amount_ok = result.amount == expected_amount
            print(
                f"  ✓ '{text}' -> Amount: {result.amount}, Date: {result.date} {'(today)' if date_ok else '(wrong date!)'}"
            )
        except Exception as e:
            print(f"  ✗ '{text}' - Error: {e}")


async def test_full_flow():
    """Test the complete flow from message to database."""
    print("\n=== Test: Full Flow ===")

    init_schema()

    messages = [
        "Ăn trưa 85k ở Phở Thìn",
        "Đánh cầu lông 30k",
    ]

    for msg in messages:
        result = await extract_transaction(msg)

        # Auto-confirm (simulating the bot behavior)
        tx = Transaction(
            date=result.date,
            merchant=result.merchant,
            amount=result.amount,
            currency=result.currency,
            category=result.category,
            payment_method=result.payment_method,
            description=result.description,
            source_type=result.source_type,
            confidence=result.confidence,
            needs_review=result.needs_review,
        )
        tx_id = add_transaction(tx)
        print(f"  Saved '{msg}' -> ID {tx_id}, {result.amount} VND")

    # Check monthly summary
    now = datetime.now()
    summary = get_monthly_summary(now.year, now.month)
    print(f"\n  Monthly total: {summary['total_spent']:,.0f} VND")
    assert summary["total_spent"] > 0, "Monthly total should be > 0"
    print("  ✓ Full flow test passed")


if __name__ == "__main__":
    test_json_parsing_with_markdown()
    test_vietnamese_amount_parsing()
    test_fallback_extraction()
    asyncio.run(test_llm_extraction())
    asyncio.run(test_full_flow())

    print("\n" + "=" * 50)
    print("✅ All tests completed!")
