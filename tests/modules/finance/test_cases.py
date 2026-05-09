"""Tests for Finance module."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.core.database import (
    Transaction,
    add_transaction,
    find_duplicates,
    init_schema,
)
from app.modules.finance.extractor import extract_simple_fallback


def test_text_input_formats():
    """Test text input with various formats."""
    print("=== Text Input Format Tests ===")

    test_cases = [
        # (text, expected_amount_contains, expected_merchant_contains)
        ("Ăn trưa 85k ở Phở Thìn", 85000, "Phở"),
        ("cà phê 55k tại The Coffee House", 55000, "Coffee House"),
        ("GrabBike 45k", 45000, "GrabBike"),
        ("2.5tr internet VNPT", 2500000, "VNPT"),
        ("Netflix 260k/tháng", 260000, "Netflix"),
        ("Ăn tối 120,000 VND tại nhà hàng", 120000, "nhà hàng"),
        ("Mua sắm 1,500,000 VND", 1500000, None),
    ]

    passed = 0
    for text, expected_amount, expected_merchant in test_cases:
        result = extract_simple_fallback(text)
        if result and result.amount == expected_amount:
            if (
                expected_merchant is None
                or expected_merchant.lower() in (result.merchant or "").lower()
            ):
                print(
                    f"✓ '{text}' -> Amount: {result.amount}, Merchant: {result.merchant}"
                )
                passed += 1
            else:
                print(
                    f"✗ '{text}' -> Expected merchant containing '{expected_merchant}', got '{result.merchant}'"
                )
        else:
            print(
                f"✗ '{text}' -> Expected {expected_amount}, got {result.amount if result else 'None'}"
            )

    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_duplicate_detection():
    """Test duplicate detection."""
    print("\n=== Duplicate Detection Tests ===")

    init_schema()

    # Add test transactions
    t1 = Transaction(
        date="2025-01-15",
        merchant="Highlands Coffee",
        amount=65000,
        currency="VND",
        category="Coffee",
        payment_method="Card",
        description="Test",
        source_type="text",
        confidence=1.0,
        needs_review=False,
    )
    add_transaction(t1)

    # Find duplicates
    duplicates = find_duplicates("Highlands Coffee", 65000, "2025-01-15")

    if len(duplicates) > 0:
        print(f"✓ Duplicate detection works: Found {len(duplicates)} duplicate(s)")
        return True
    else:
        print("✗ Duplicate detection failed: No duplicates found")
        return False


def test_invalid_input():
    """Test invalid input handling."""
    print("\n=== Invalid Input Tests ===")

    invalid_inputs = [
        "",
        "   ",
        "hello world",  # No amount
        "xyz",
    ]

    passed = 0
    for text in invalid_inputs:
        result = extract_simple_fallback(text)
        if result is None:
            print(f"✓ Invalid input '{text}' correctly rejected")
            passed += 1
        else:
            print(f"✗ Invalid input '{text}' incorrectly accepted")

    print(f"\nPassed: {passed}/{len(invalid_inputs)}")
    return passed == len(invalid_inputs)


if __name__ == "__main__":
    results = []
    results.append(test_text_input_formats())
    results.append(test_duplicate_detection())
    results.append(test_invalid_input())

    print("\n" + "=" * 50)
    if all(results):
        print("✅ All test cases passed!")
    else:
        print("❌ Some tests failed")