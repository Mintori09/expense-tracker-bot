"""
LLM-based transaction extraction module.
"""

import json
import logging
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.shared.date_utils import resolve_relative_dates
from app.shared.exceptions import ExtractionError

logger = logging.getLogger(__name__)

# Merchant to category mapping for learning
_merchant_category_map = settings.merchant_category_map.copy()


def get_category_for_merchant(merchant: str) -> Optional[str]:
    """Get learned category for a merchant."""
    if merchant:
        merchant_lower = merchant.lower().strip()
        for known_merchant, category in _merchant_category_map.items():
            if (
                known_merchant.lower() in merchant_lower
                or merchant_lower in known_merchant.lower()
            ):
                return category
    return None


def learn_merchant_category(merchant: str, category: str) -> None:
    """Learn a new merchant-category mapping."""
    if merchant and category:
        _merchant_category_map[merchant] = category
        logger.info(f"Learned: {merchant} -> {category}")


class ExtractedTransaction(BaseModel):
    """Extracted transaction data with validation."""

    date: str
    merchant: Optional[str] = None
    amount: float = Field(gt=0)
    currency: str = "VND"
    category: str = "Other"
    payment_method: str = "Chuyển khoản"
    description: str = ""
    source_type: str = "text"
    confidence: float = Field(ge=0, le=1, default=0.9)
    needs_review: bool = False
    user_id: Optional[int] = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Invalid date format, expected YYYY-MM-DD")
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        valid_categories = [
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
        if v not in valid_categories:
            return "Other"
        return v


def parse_vietnamese_amount(text: str) -> Optional[float]:
    """Parse Vietnamese amount format like '85k', '2.5tr', '100,000'."""
    text = text.lower().strip()

    # Match patterns like "85k", "85.5k", "2tr", "2.5tr"
    k_match = re.search(r"(\d+(?:[.,]\d+)?)\s*k", text)
    tr_match = re.search(r"(\d+(?:[.,]\d+)?)\s*tr", text)

    if k_match:
        return float(k_match.group(1).replace(",", ".")) * 1000
    elif tr_match:
        return float(tr_match.group(1).replace(",", ".")) * 1000000
    else:
        # Try standard number format - handle both 100,000 and 100.000
        num_match = re.search(r"(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)", text)
        if num_match:
            num_str = num_match.group(1)
            # Remove dots (thousand separators) and replace comma with dot for decimal
            if "." in num_str and "," not in num_str:
                # Format: 100.000 (Vietnamese style with dots as thousand separators)
                num_str = num_str.replace(".", "")
            elif "," in num_str and "." not in num_str:
                # Format: 100,000 (Western style)
                num_str = num_str.replace(",", "")
            elif "," in num_str and "." in num_str:
                # Format: 100,000.00 or 100.000,00 - assume comma is decimal
                num_str = num_str.replace(".", "").replace(",", ".")
            return float(num_str)

    return None


# USD to VND exchange rate (approximate, can be updated dynamically)
USD_TO_VND_RATE = 25000
_usd_rate_cache = {"rate": USD_TO_VND_RATE, "timestamp": None}


def set_usd_to_vnd_rate(rate: float) -> None:
    """Update the USD to VND rate."""
    global USD_TO_VND_RATE
    USD_TO_VND_RATE = rate
    _usd_rate_cache["rate"] = rate


async def get_usd_to_vnd_rate() -> float:
    """Fetch current USD to VND exchange rate from external API.

    Uses Vietcombank API or falls back to cached/fixed rate.
    """
    import time

    # Check cache - refresh every hour
    now = time.time()
    if _usd_rate_cache["timestamp"] and (now - _usd_rate_cache["timestamp"]) < 3600:
        return _usd_rate_cache["rate"]

    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try Vietcombank API
            response = await client.get(
                "https://vapi.vn/app_devices/api/v1/dothi/bank/vietcombank"
            )
            if response.status_code == 200:
                data = response.json()
                if "results" in data and len(data["results"]) > 0:
                    rate = float(data["results"][0].get("transfer_usd_sell", 0))
                    if rate > 0:
                        _usd_rate_cache["rate"] = rate
                        _usd_rate_cache["timestamp"] = now
                        return rate
    except Exception as e:
        logger.warning(f"Failed to fetch USD rate: {e}")

    return _usd_rate_cache["rate"]


def parse_usd_amount(text: str) -> tuple[Optional[float], Optional[str]]:
    """Parse USD amount format like '$10', '10 USD', '10 dollars'.

    Returns:
        Tuple of (amount_in_vnd, currency_code) or (None, None) if not USD
    """
    text_lower = text.lower().strip()

    # Match patterns: $10, $10.50, 10$, 10 usd, 10 dollars
    usd_patterns = [
        r"\$(\d+(?:[.,]\d+)?)",  # $10, $10.50
        r"(\d+(?:[.,]\d+)?)\s*\$",  # 10$, 10.50$
        r"(\d+(?:[.,]\d+)?)\s*usd",  # 10 USD
        r"(\d+(?:[.,]\d+)?)\s*dollars?",  # 10 dollars
    ]

    for pattern in usd_patterns:
        match = re.search(pattern, text_lower)
        if match:
            usd_amount = float(match.group(1).replace(",", "."))
            vnd_amount = usd_amount * USD_TO_VND_RATE
            return vnd_amount, "USD"

    return None, None


async def call_llm(prompt: str) -> str:
    """Call LLM API to get response."""

    from app.config import get_llm_client, settings

    logger.info("=== LLM API call ===")
    logger.info(f"Provider: {settings.llm_provider}, Model: {settings.llm_model}")
    logger.info(f"Prompt: {prompt[:100]}...")

    client = get_llm_client()

    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=500,
    )

    result = response.choices[0].message.content
    logger.info(
        f"API response ID: {response.id}, tokens: {response.usage.total_tokens}"
    )
    logger.info(f"Raw response: {result[:200] if result else 'None'}...")
    logger.info("=== LLM API completed ===")

    return result


def get_system_prompt() -> str:
    """Get the system prompt for LLM extraction."""
    return """You are a finance data extraction assistant.

Extract one financial transaction from the user input.

Return only valid JSON with this schema:

{
  "date": "YYYY-MM-DD",
  "merchant": "string or null",
  "amount": number,
  "currency": "VND",
  "category": "Food | Coffee | Groceries | Transport | Rent | Utilities | Shopping | Health | Education | Entertainment | Travel | Subscription | Income | Other",
  "payment_method": "Cash | Bank Transfer | Card | E-wallet | Unknown",
  "description": "short description",
  "confidence": number between 0 and 1,
  "needs_review": boolean
}

Rules:
- If the date is missing, use today's date.
- Convert "k" to thousand VND (e.g., "85k" = 85000).
- If amount is unclear, set needs_review to true.
- Do not invent merchant names.
- Return JSON only.
"""


async def extract_transactions(
    text: str, source_type: str = "text"
) -> list[ExtractedTransaction]:
    """Extract multiple transactions from invoice/receipt text using LLM."""
    logger.info(
        f"=== Extracting transactions from: '{text[:100]}...' (source: {source_type})"
    )

    # Pre-process text to resolve Vietnamese relative dates
    text, resolved_date = resolve_relative_dates(text)
    if resolved_date:
        logger.info(f"Resolved relative date in text: {resolved_date}")

    system_prompt = """You are a finance data extraction assistant.

Extract ALL items from the invoice/receipt. Each line item is a separate transaction.

Return JSON array with this schema:
[
  {
    "date": "YYYY-MM-DD",
    "merchant": "string or null",
    "amount": number,
    "currency": "VND",
    "category": "Food | Coffee | Groceries | Transport | Rent | Utilities | Shopping | Health | Education | Entertainment | Travel | Subscription | Income | Other",
    "payment_method": "Cash | Bank Transfer | Card | E-wallet | Unknown",
    "description": "item description"
  }
]

Rules:
- If date missing, use today's date
- Convert "k" to thousand VND (e.g., "85k" = 85000)
- Use the same merchant for all items
- If no specific date mentioned, use today
- Return valid JSON array only"""

    try:
        from app.config import get_llm_client, settings

        client = get_llm_client()

        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            temperature=0.1,
            max_tokens=1000,
        )

        result_text = response.choices[0].message.content or "[]"
        logger.info(f"Multi-transaction API response: {result_text[:200]}")

        # Parse as array
        data = json.loads(result_text.strip())

        transactions = []
        from app.shared.date_utils import VIETNAM_TZ
        today = datetime.now(VIETNAM_TZ).strftime("%Y-%m-%d")

        for item in data:
            try:
                item_date = item.get("date")
                # Use resolved date if no date provided
                if not item_date:
                    item_date = resolved_date or today

                tx = ExtractedTransaction(
                    date=item_date,
                    merchant=item.get("merchant"),
                    amount=float(item.get("amount", 0)),
                    currency=item.get("currency", "VND"),
                    category=item.get("category", "Other"),
                    payment_method=item.get("payment_method", "Chuyển khoản"),
                    description=item.get("description", ""),
                    source_type=source_type,
                    confidence=0.9,
                    needs_review=False,
                )
                transactions.append(tx)
            except Exception as e:
                logger.warning(f"Failed to parse item: {item}, error: {e}")

        logger.info(f"=== Extracted {len(transactions)} transactions ===")
        return transactions

    except Exception as e:
        logger.error(f"Multi-transaction extraction failed: {e}")
        return []  # Return empty list to fall back to single transaction


async def extract_transaction(
    text: str, source_type: str = "text"
) -> ExtractedTransaction:
    """Extract transaction data from text using LLM."""
    logger.info(
        f"=== Extracting transaction from: '{text[:50]}...' (source: {source_type})"
    )

    # Pre-process text to resolve Vietnamese relative dates
    text, resolved_date = resolve_relative_dates(text)
    if resolved_date:
        logger.info(f"Resolved relative date in text: {resolved_date}")

    try:
        response = await call_llm(text)

        # Strip markdown code blocks if present
        cleaned_response = re.sub(r"```json\s*|\s*```", "", response).strip()
        logger.info(f"LLM cleaned response: {cleaned_response[:100]}...")

        # Parse JSON response
        data = json.loads(cleaned_response)

        # Validate required fields
        if "amount" not in data:
            raise ExtractionError("Missing amount in extraction")

        # Parse date - use resolved_date or today if missing or invalid
        date = data.get("date")
        from app.shared.date_utils import VIETNAM_TZ
        today = datetime.now(VIETNAM_TZ).strftime("%Y-%m-%d")

        # If we resolved a relative date from the text, use it as the default
        if not date:
            date = resolved_date or today
        else:
            # Validate date is reasonable (not in the future, not too old)
            try:
                parsed_date = datetime.strptime(date, "%Y-%m-%d")
                today_dt = datetime.now(VIETNAM_TZ)
                # If date is in future or more than 30 days ago, use resolved or today
                if (
                    parsed_date.date() > today_dt.date()
                    or (today_dt.date() - parsed_date.date()).days > 30
                ):
                    date = resolved_date or today
            except ValueError:
                date = resolved_date or today

        # Ensure amount is float
        amount = float(data["amount"])
        confidence = float(data.get("confidence", 0.9))

        # Determine if needs review
        needs_review = data.get("needs_review", False)
        if confidence < 0.7:
            needs_review = True

        result = ExtractedTransaction(
            date=date,
            merchant=data.get("merchant"),
            amount=amount,
            currency=data.get("currency", "VND"),
            category=data.get("category", "Other"),
            payment_method=data.get("payment_method", "Chuyển khoản"),
            description=data.get("description", ""),
            source_type=source_type,
            confidence=confidence,
            needs_review=needs_review,
        )

        logger.info(
            f"=== Extracted: {result.merchant} - {result.amount} - {result.category} ==="
        )
        return result

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}, response was: {response[:100]}")
        raise ExtractionError("Failed to parse LLM response")
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        raise ExtractionError(str(e))


def extract_simple_fallback(text: str) -> Optional[ExtractedTransaction]:
    """Simple fallback extraction without LLM for common Vietnamese patterns."""
    from app.shared.date_utils import VIETNAM_TZ, parse_vietnamese_date

    # Clean text
    text = text.strip()

    # Try to parse Vietnamese relative date from the beginning of the text
    date = parse_vietnamese_date(text)
    if date is None:
        date = datetime.now(VIETNAM_TZ).strftime("%Y-%m-%d")

    # Find amount first - check USD first, then VND
    amount = None
    merchant_text = text
    detected_currency = "VND"

    # Try to find USD amount
    usd_amount, usd_currency = parse_usd_amount(text)
    if usd_amount:
        amount = usd_amount
        detected_currency = usd_currency
        # Remove USD pattern from text
        for pattern in [r"\$(\d+(?:[.,]\d+)?)", r"(\d+(?:[.,]\d+)?)\s*\$", r"(\d+(?:[.,]\d+)?)\s*usd", r"(\d+(?:[.,]\d+)?)\s*dollars?"]:
            merchant_text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    else:
        # Try to find amount with k or tr suffix first
        k_match = re.search(r"(\d+(?:[.,]\d+)?)\s*k", text, re.IGNORECASE)
        tr_match = re.search(r"(\d+(?:[.,]\d+)?)\s*tr", text, re.IGNORECASE)

        if k_match:
            amount = float(k_match.group(1).replace(",", ".")) * 1000
            merchant_text = (text[: k_match.start()] + " " + text[k_match.end() :]).strip()
        elif tr_match:
            amount = float(tr_match.group(1).replace(",", ".")) * 1000000
            merchant_text = (text[: tr_match.start()] + " " + text[tr_match.end() :]).strip()
        else:
            # Try standard number format
            num_match = re.search(r"(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)", text)
            if num_match:
                num_str = num_match.group(1)
                if "." in num_str and "," not in num_str:
                    num_str = num_str.replace(".", "")
                elif "," in num_str and "." not in num_str:
                    num_str = num_str.replace(",", "")
                amount = float(num_str)
                merchant_text = (
                    text[: num_match.start()] + " " + text[num_match.end() :]
                ).strip()

    if amount and amount > 0:
        # Clean up merchant name - remove common prefixes (Vietnamese verbs/phrases and date expressions)
        merchant = re.sub(
            r"\b(ăn|mua|chi|pay|paid|spent|giao\s?dịch|sáng|trưa|chiều|đêm|tối|cà\s?phê|internet|hôm qua|hôm kia|ngày mai|mống mai|hôm nay|nay|ngày này tháng trước|ngày này tuần trước|ngày này năm trước)\b\s*",
            "",
            merchant_text,
            flags=re.IGNORECASE,
        )
        merchant = re.sub(r"\s*(?:vnd|đồng)\b", "", merchant, flags=re.IGNORECASE)
        merchant = re.sub(r"\s+(?:ở|tại)\s+", " ", merchant, flags=re.IGNORECASE)
        merchant = re.sub(r"^(?:ở|tại)\s+", "", merchant, flags=re.IGNORECASE)
        merchant = re.sub(r"\s*/tháng\s*$", "", merchant, flags=re.IGNORECASE)
        merchant = re.sub(r"\s+", " ", merchant).strip(" -:/")

        if not merchant or merchant.lower() in ["vnd", "đồng"]:
            merchant = "Unknown"

        category = get_category_for_merchant(merchant) or "Other"

        return ExtractedTransaction(
            date=date,
            merchant=merchant if merchant else None,
            amount=amount,
            currency="VND",
            category=category,
            payment_method="Chuyển khoản",
            description=text[:50],
            source_type="text",
            confidence=0.7,
            needs_review=(category == "Other"),
        )

    return None


def extract_multiple_fallback(text: str) -> list[ExtractedTransaction]:
    """Extract multiple transactions from text with comma-separated amounts.

    Example: "30k đánh cầu sân win win, 50k đánh cầu sân lâm gia"
    Returns: [30k transaction, 50k transaction]
    """
    from app.shared.date_utils import VIETNAM_TZ, parse_vietnamese_date

    transactions = []

    # Try to parse Vietnamese relative date from the text
    date = parse_vietnamese_date(text)
    if date is None:
        date = datetime.now(VIETNAM_TZ).strftime("%Y-%m-%d")

    # Find all k/tr amounts in the text
    k_matches = list(re.finditer(r"(\d+(?:[.,]\d+)?)\s*k", text, re.IGNORECASE))
    tr_matches = list(re.finditer(r"(\d+(?:[.,]\d+)?)\s*tr", text, re.IGNORECASE))

    # Combine and sort by position
    all_matches = [(m.start(), "k", m) for m in k_matches] + [
        (m.start(), "tr", m) for m in tr_matches
    ]
    all_matches.sort(key=lambda x: x[0])

    if len(all_matches) <= 1:
        return transactions  # Not multiple transactions

    for i, (pos, type_, match) in enumerate(all_matches):
        if type_ == "k":
            amount = float(match.group(1).replace(",", ".")) * 1000
        else:
            amount = float(match.group(1).replace(",", ".")) * 1000000

        # Extract text between this match and the next one (or end of string)
        start_pos = match.end()
        if i + 1 < len(all_matches):
            end_pos = all_matches[i + 1][2].start()
        else:
            end_pos = len(text)

        item_text = text[start_pos:end_pos].strip(" ,;-")

        # Clean up the item text
        item_text = re.sub(r"\s+", " ", item_text).strip()

        if item_text:
            transactions.append(
                ExtractedTransaction(
                    date=date,
                    merchant=None,
                    amount=amount,
                    currency="VND",
                    category="Other",
                    payment_method="Chuyển khoản",
                    description=item_text[:50],
                    source_type="text",
                    confidence=0.7,
                    needs_review=True,
                )
            )

    return transactions

