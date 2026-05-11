"""
LLM-based transaction extraction module.

Features:
- Extract single or multiple Vietnamese financial transactions.
- Supports LLM extraction with robust JSON parsing.
- Falls back to deterministic regex extraction.
- Supports VND and USD conversion.
- Normalizes category, payment method, merchant, date, and amount.
"""

import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.shared.date_utils import (
    VIETNAM_TZ,
    extract_date_from_text,
    parse_vietnamese_date,
    resolve_relative_dates,
)
from app.shared.exceptions import ExtractionError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

VALID_CATEGORIES = {
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
}

VALID_PAYMENT_METHODS = {
    "Cash",
    "Bank Transfer",
    "Card",
    "E-wallet",
    "Unknown",
}

ACTION_WORDS = [
    "mua",
    "uống",
    "ăn",
    "trả",
    "đóng",
    "thanh toán",
    "chuyển",
    "nạp",
    "đặt",
    "đi",
    "dùng",
    "xài",
    "tốn",
    "hết",
    "mất",
    "chi",
    "cho",
    "tại",
]

USD_TO_VND_RATE = 25_000
_usd_rate_cache: dict[str, Any] = {
    "rate": USD_TO_VND_RATE,
    "timestamp": None,
}

_merchant_category_map = settings.merchant_category_map.copy()


# ---------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------


class ExtractedTransaction(BaseModel):
    """Normalized extracted transaction data."""

    date: str = Field(
        default_factory=lambda: datetime.now(VIETNAM_TZ).strftime("%Y-%m-%d")
    )
    merchant: Optional[str] = None
    amount: float = Field(ge=0)
    currency: str = "VND"
    original_currency: Optional[str] = None
    category: str = "Other"
    payment_method: str = "Unknown"
    description: str = ""
    source_type: str = "text"
    confidence: float = Field(ge=0, le=1, default=0.9)
    needs_review: bool = False
    user_id: Optional[int] = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("Invalid date format, expected YYYY-MM-DD") from exc
        return value

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        # App stores everything as VND.
        return "VND"

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        return value if value in VALID_CATEGORIES else "Other"

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, value: str) -> str:
        mapping = {
            "cash": "Cash",
            "tiền mặt": "Cash",
            "bank transfer": "Bank Transfer",
            "chuyển khoản": "Bank Transfer",
            "ck": "Bank Transfer",
            "banking": "Bank Transfer",
            "card": "Card",
            "thẻ": "Card",
            "visa": "Card",
            "mastercard": "Card",
            "e-wallet": "E-wallet",
            "ewallet": "E-wallet",
            "ví điện tử": "E-wallet",
            "momo": "E-wallet",
            "zalopay": "E-wallet",
            "shopeepay": "E-wallet",
            "unknown": "Unknown",
            "": "Unknown",
        }

        normalized = str(value or "").strip()
        return mapping.get(
            normalized.lower(),
            normalized if normalized in VALID_PAYMENT_METHODS else "Unknown",
        )


# ---------------------------------------------------------------------
# Category and merchant helpers
# ---------------------------------------------------------------------


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def clean_merchant_text(text: str) -> str:
    cleaned = normalize_text(text)

    for word in ACTION_WORDS:
        cleaned = re.sub(rf"\b{re.escape(word)}\b", " ", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(
        r"\b(vnd|vnđ|đồng|usd|dollars?|nghìn|ngàn|triệu)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-:;")

    return cleaned


def title_merchant(merchant: Optional[str]) -> Optional[str]:
    if not merchant:
        return None

    merchant = normalize_text(merchant)
    if not merchant:
        return None

    known_upper = {
        "fpt",
        "vnpt",
        "gpt",
        "chatgpt",
        "youtube",
        "netflix",
        "spotify",
        "momo",
        "zalopay",
        "shopeepay",
        "grab",
        "be",
        "opencode",
    }

    if merchant.lower() in known_upper:
        return merchant.upper() if len(merchant) <= 4 else merchant.title()

    return merchant[:1].upper() + merchant[1:]


def get_category_for_keywords(text: str) -> Optional[str]:
    text_lower = (text or "").lower()

    keyword_rules = [
        (
            "Coffee",
            [
                "cà phê",
                "cafe",
                "coffee",
                "trà sữa",
                "highlands",
                "phúc long",
                "starbucks",
            ],
        ),
        (
            "Food",
            ["phở", "bún", "bánh mì", "cơm", "com", "nhà hàng", "quán ăn", "đồ ăn"],
        ),
        (
            "Groceries",
            ["siêu thị", "chợ", "rau", "thịt", "cá", "sữa", "tạp hóa", "groceries"],
        ),
        (
            "Transport",
            ["grab", "grabbike", "be", "taxi", "xe ôm", "bus", "xăng", "gửi xe"],
        ),
        ("Rent", ["tiền nhà", "thuê nhà", "phòng trọ", "rent"]),
        (
            "Utilities",
            [
                "điện",
                "nước",
                "internet",
                "wifi",
                "vnpt",
                "fpt",
                "viettel",
                "điện thoại",
            ],
        ),
        (
            "Shopping",
            ["shopee", "lazada", "tiki", "mua đồ", "quần áo", "giày", "shopping"],
        ),
        ("Health", ["thuốc", "bệnh viện", "khám", "nha khoa", "nhà thuốc"]),
        ("Education", ["học phí", "khóa học", "sách", "udemy", "coursera"]),
        ("Entertainment", ["phim", "game", "karaoke", "vé xem phim"]),
        ("Travel", ["khách sạn", "vé máy bay", "du lịch", "booking"]),
        (
            "Subscription",
            [
                "netflix",
                "youtube premium",
                "spotify",
                "icloud",
                "chatgpt",
                "opencode",
                "gpt",
                "gemini",
                "claude",
                "cursor",
                "subscription",
                "saas",
                "app",
                "software",
            ],
        ),
        ("Income", ["lương", "nhận tiền", "được trả", "thu nhập", "thưởng"]),
    ]

    for category, keywords in keyword_rules:
        if any(keyword in text_lower for keyword in keywords):
            return category

    if re.search(r"\b(ăn|uống)\b", text_lower):
        return "Food"

    return None


def get_category_for_merchant(merchant: Optional[str]) -> Optional[str]:
    if not merchant:
        return None

    merchant_lower = merchant.lower().strip()

    for known_merchant, category in _merchant_category_map.items():
        known_lower = known_merchant.lower().strip()

        # Avoid overly broad matching for very short merchant names.
        if len(known_lower) < 3:
            continue

        if known_lower == merchant_lower:
            return category

        if known_lower in merchant_lower:
            return category

    return get_category_for_keywords(merchant_lower)


def learn_merchant_category(merchant: str, category: str) -> None:
    """Learn a merchant-category mapping in memory.

    Note: This is not persistent. Persist to DB if long-term learning is required.
    """
    if merchant and category in VALID_CATEGORIES:
        _merchant_category_map[merchant] = category
        logger.info("Learned merchant category mapping: %s -> %s", merchant, category)


# ---------------------------------------------------------------------
# Amount parsing
# ---------------------------------------------------------------------


def parse_vietnamese_amount(text: str) -> Optional[float]:
    """Parse Vietnamese amount formats.

    Supported:
    - 85k -> 85000
    - 2.5tr -> 2500000
    - 1tr2 -> 1200000
    - 25 nghìn / 25 ngàn -> 25000
    - 1 triệu / 1.2 triệu -> 1000000 / 1200000
    - 100,000 / 100.000 -> 100000
    """
    if not text:
        return None

    text_lower = text.lower().strip()

    # 1tr2, 2tr5
    mixed_tr_match = re.search(r"\b(\d+)\s*tr\s*(\d+)\b", text_lower)
    if mixed_tr_match:
        million = float(mixed_tr_match.group(1))
        decimal_part = mixed_tr_match.group(2)
        decimal_value = float(f"0.{decimal_part}")
        return (million + decimal_value) * 1_000_000

    # 85k, 85.5k
    k_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*k\b", text_lower)
    if k_match:
        return float(k_match.group(1).replace(",", ".")) * 1_000

    # 2tr, 2.5tr
    tr_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*tr\b", text_lower)
    if tr_match:
        return float(tr_match.group(1).replace(",", ".")) * 1_000_000

    # 25 nghìn, 25 ngàn
    thousand_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(nghìn|ngàn)\b", text_lower)
    if thousand_match:
        return float(thousand_match.group(1).replace(",", ".")) * 1_000

    # 1 triệu, 1.2 triệu
    million_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*triệu\b", text_lower)
    if million_match:
        return float(million_match.group(1).replace(",", ".")) * 1_000_000

    # Standard thousand-separated numbers: 100,000 / 100.000 / 1,000,000
    separated_match = re.search(r"\b\d{1,3}(?:[.,]\d{3})+\b", text_lower)
    if separated_match:
        num_str = separated_match.group(0)
        return float(num_str.replace(".", "").replace(",", ""))

    # Plain integer only.
    integer_match = re.search(r"\b\d+\b", text_lower)
    if integer_match:
        return float(integer_match.group(0))

    return None


def parse_usd_amount(
    text: str,
    rate: Optional[float] = None,
) -> tuple[Optional[float], Optional[str]]:
    """Parse USD amount and convert to VND.

    Returns:
        (amount_in_vnd, original_currency)
    """
    if not text:
        return None, None

    text_lower = text.lower().strip()

    usd_patterns = [
        r"\$(\d+(?:[.,]\d+)?)",
        r"\b(\d+(?:[.,]\d+)?)\s*\$",
        r"\b(\d+(?:[.,]\d+)?)\s*usd\b",
        r"\b(\d+(?:[.,]\d+)?)\s*dollars?\b",
    ]

    for pattern in usd_patterns:
        match = re.search(pattern, text_lower)
        if match:
            usd_amount = float(match.group(1).replace(",", "."))
            return usd_amount * float(rate or USD_TO_VND_RATE), "USD"

    return None, None


def remove_amount_from_text(text: str) -> str:
    patterns = [
        r"\b\d+\s*tr\s*\d+\b",
        r"\b\d+(?:[.,]\d+)?\s*k\b",
        r"\b\d+(?:[.,]\d+)?\s*tr\b",
        r"\b\d+(?:[.,]\d+)?\s*(nghìn|ngàn|triệu)\b",
        r"\$\d+(?:[.,]\d+)?",
        r"\b\d+(?:[.,]\d+)?\s*\$",
        r"\b\d+(?:[.,]\d+)?\s*usd\b",
        r"\b\d+(?:[.,]\d+)?\s*dollars?\b",
        r"\b\d{1,3}(?:[.,]\d{3})+\b",
    ]

    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

    return normalize_text(cleaned)


# ---------------------------------------------------------------------
# Exchange rate
# ---------------------------------------------------------------------


def set_usd_to_vnd_rate(rate: float) -> None:
    global USD_TO_VND_RATE

    if rate <= 0:
        raise ValueError("USD to VND rate must be positive")

    USD_TO_VND_RATE = rate
    _usd_rate_cache["rate"] = rate
    _usd_rate_cache["timestamp"] = time.time()


async def get_usd_to_vnd_rate() -> float:
    """Fetch current USD to VND exchange rate, with cache and fallback."""
    now = time.time()
    cached_timestamp = _usd_rate_cache.get("timestamp")

    if cached_timestamp and now - cached_timestamp < 3600:
        return float(_usd_rate_cache["rate"])

    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("https://open.er-api.com/v6/latest/USD")

        if response.status_code == 200:
            data = response.json()
            rate = float(data.get("rates", {}).get("VND", 0))

            if data.get("result") == "success" and rate > 0:
                _usd_rate_cache["rate"] = rate
                _usd_rate_cache["timestamp"] = now
                logger.info("Updated USD/VND rate: %s", rate)
                return rate

    except Exception as exc:
        logger.warning("Failed to fetch USD/VND rate, using fallback: %s", exc)

    return float(_usd_rate_cache["rate"])


# ---------------------------------------------------------------------
# Payment method
# ---------------------------------------------------------------------


def infer_payment_method(text: str) -> str:
    text_lower = (text or "").lower()

    if any(keyword in text_lower for keyword in ["tiền mặt", "cash"]):
        return "Cash"

    if any(
        keyword in text_lower
        for keyword in ["chuyển khoản", " ck ", "banking", "ngân hàng"]
    ):
        return "Bank Transfer"

    if any(
        keyword in text_lower
        for keyword in [" thẻ ", "credit card", "debit card", "visa", "mastercard"]
    ):
        return "Card"

    if any(
        keyword in text_lower
        for keyword in ["momo", "zalopay", "shopeepay", "ví điện tử"]
    ):
        return "E-wallet"

    return "Unknown"


# ---------------------------------------------------------------------
# LLM prompt and JSON handling
# ---------------------------------------------------------------------


def get_system_prompt(multiple: bool = False) -> str:
    if multiple:
        output_instruction = """
Extract all financial transactions from the user input.

Return only a valid JSON array.
Each item in the array must follow this schema:
"""
    else:
        output_instruction = """
Extract exactly one financial transaction from the user input.

Return only a valid JSON object with this schema:
"""

    return f"""
You are a finance data extraction assistant for Vietnamese users.

{output_instruction}

{{
  "date": "YYYY-MM-DD",
  "merchant": "string or null",
  "amount": number,
  "currency": "VND",
  "original_currency": "VND | USD | null",
  "category": "Food | Coffee | Groceries | Transport | Rent | Utilities | Shopping | Health | Education | Entertainment | Travel | Subscription | Income | Other",
  "payment_method": "Cash | Bank Transfer | Card | E-wallet | Unknown",
  "description": "short description",
  "confidence": number between 0 and 1,
  "needs_review": boolean
}}

Rules:

1. Date
- If the date is missing, use today's date.
- Convert Vietnamese relative dates:
  - "hôm nay" = today
  - "hôm qua" = yesterday
  - "mai" / "ngày mai" = tomorrow
- Output date as YYYY-MM-DD.

2. Amount and currency
- The final stored currency must always be "VND".
- If the input is USD, convert to VND using approximate market rate if available.
- Set "original_currency" to "USD" if the input was USD, otherwise "VND".
- Convert "k" to thousand VND:
  - "25k" = 25000
  - "85k" = 85000
- Handle Vietnamese amount formats:
  - "25 nghìn" = 25000
  - "25 ngàn" = 25000
  - "1 triệu" = 1000000
  - "1tr2" = 1200000
  - "1.2 triệu" = 1200000
- If amount is missing or unclear:
  - amount = 0
  - needs_review = true

3. Merchant extraction
- Merchant is the business, app, service, store, brand, product provider, or place related to the transaction.
- Remove action verbs from merchant:
  mua, uống, ăn, trả, thanh toán, chuyển, nạp, đặt, đi, dùng, xài, tốn, hết, mất, chi.
- Keep named brands, apps, services, stores, or places.
- Do not use action verbs as merchant.
- Do not invent merchant names.
- If no merchant/place/brand/service is specified, use null.
- If only a generic place is mentioned, merchant can be:
  - "quán cà phê"
  - "quán ăn"
  - "siêu thị"
  - "nhà thuốc"
  - "cửa hàng"

Examples:
- "mua Opencode go tốn 5 usd" -> merchant: "Opencode go"
- "trả Netflix 260k" -> merchant: "Netflix"
- "uống cà phê Highlands 45k" -> merchant: "Highlands"
- "ăn phở quán gần nhà 40k" -> merchant: "quán gần nhà"
- "mua rau 30k" -> merchant: null
- "đi Grab 70k" -> merchant: "Grab"
- "nạp MoMo 100k" -> merchant: "MoMo"

4. Category
Choose the most appropriate category:
- Coffee: cà phê, cafe, trà sữa, Highlands, Phúc Long, Starbucks
- Food: ăn, cơm, phở, bún, bánh mì, nhà hàng, đồ ăn
- Groceries: siêu thị, chợ, rau, thịt, cá, sữa, tạp hóa
- Transport: Grab, Be, taxi, xe ôm, bus, xăng, gửi xe
- Rent: tiền nhà, thuê nhà, phòng trọ
- Utilities: điện, nước, internet, wifi, điện thoại
- Shopping: mua đồ, quần áo, giày, Shopee, Lazada, Tiki
- Health: thuốc, bệnh viện, khám, nha khoa, nhà thuốc
- Education: học phí, khóa học, sách, Udemy, Coursera
- Entertainment: phim, game, karaoke, vé xem phim
- Travel: khách sạn, vé máy bay, du lịch, booking
- Subscription: Netflix, Spotify, YouTube Premium, iCloud, ChatGPT, app subscription, SaaS, phần mềm
- Income: lương, nhận tiền, được trả, thu nhập, thưởng
- Other: when no category fits

5. Payment method
Infer payment method only when clearly stated:
- Cash: tiền mặt, cash
- Bank Transfer: chuyển khoản, ck, banking, ngân hàng
- Card: thẻ, credit card, debit card, visa, mastercard
- E-wallet: MoMo, ZaloPay, ShopeePay, ví điện tử
- Unknown: if not specified

6. Description
- Write a concise Vietnamese or mixed-language description.
- Do not add unnecessary verbs.
- Do not include the amount.

7. Confidence and review
- 0.9-1.0: clear amount, merchant/category/payment, or enough context.
- 0.7-0.89: mostly clear, but one field inferred.
- 0.5-0.69: ambiguous merchant/category.
- Below 0.5: unclear transaction.
- needs_review = true if:
  - amount is missing or unclear
  - multiple transactions appear when extracting one transaction
  - merchant/category is highly ambiguous
  - currency conversion is unclear

8. Output
- Return JSON only.
- No markdown.
- No explanation.
- No extra text.
"""


def extract_json_from_llm_response(response: str) -> Any:
    """Parse JSON from an LLM response.

    Handles:
    - Pure JSON
    - ```json code fences
    - Extra text around JSON, by extracting first object/array
    """
    if not response:
        raise ExtractionError("Empty LLM response")

    cleaned = re.sub(r"```json\s*|\s*```", "", response, flags=re.IGNORECASE).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON array first.
    array_match = re.search(r"\[[\s\S]*\]", cleaned)
    if array_match:
        try:
            return json.loads(array_match.group(0))
        except json.JSONDecodeError:
            pass

    # Try to extract JSON object.
    object_match = re.search(r"\{[\s\S]*\}", cleaned)
    if object_match:
        try:
            return json.loads(object_match.group(0))
        except json.JSONDecodeError as exc:
            raise ExtractionError(
                "Failed to parse JSON object from LLM response"
            ) from exc

    raise ExtractionError("No valid JSON found in LLM response")


async def call_llm(prompt: str, multiple: bool = False) -> str:
    """Call configured LLM API."""
    from app.config import get_llm_client, settings

    logger.info(
        "Calling LLM provider=%s model=%s", settings.llm_provider, settings.llm_model
    )

    client = get_llm_client()

    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": get_system_prompt(multiple=multiple)},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=1200 if multiple else 600,
    )

    result = response.choices[0].message.content or ""

    usage = getattr(response, "usage", None)
    if usage:
        logger.info("LLM response id=%s tokens=%s", response.id, usage.total_tokens)

    return result


# ---------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------


def today_vietnam() -> str:
    return datetime.now(VIETNAM_TZ).strftime("%Y-%m-%d")


def normalize_date(
    date_value: Optional[str], resolved_date: Optional[str] = None
) -> str:
    if not date_value:
        return resolved_date or today_vietnam()

    try:
        datetime.strptime(date_value, "%Y-%m-%d")
        return date_value
    except ValueError:
        return resolved_date or today_vietnam()


def normalize_transaction_payload(
    item: dict[str, Any],
    source_type: str = "text",
    resolved_date: Optional[str] = None,
    original_text: str = "",
) -> ExtractedTransaction:
    merchant = item.get("merchant")
    merchant = title_merchant(merchant) if merchant else None

    amount = float(item.get("amount") or 0)
    confidence = float(item.get("confidence", 0.9))

    category = item.get("category") or get_category_for_merchant(merchant)
    if not category or category not in VALID_CATEGORIES:
        category = (
            get_category_for_merchant(merchant)
            or get_category_for_keywords(original_text)
            or "Other"
        )

    payment_method = item.get("payment_method") or infer_payment_method(original_text)

    needs_review = bool(item.get("needs_review", False))
    if amount <= 0:
        needs_review = True
    if confidence < 0.7:
        needs_review = True
    if category == "Other" and not merchant:
        needs_review = True

    # Prevent LLM date hallucination:
    # - If input text has no explicit/relative date, force today.
    # - If text has date signal (or resolved_date already found), keep normalized date.
    text_date = extract_date_from_text(original_text) if original_text else None
    effective_resolved_date = resolved_date or text_date
    if effective_resolved_date:
        normalized_date = effective_resolved_date
    else:
        normalized_date = today_vietnam()

    return ExtractedTransaction(
        date=normalized_date,
        merchant=merchant,
        amount=amount,
        currency="VND",
        original_currency=item.get("original_currency")
        or item.get("currency")
        or "VND",
        category=category,
        payment_method=payment_method,
        description=normalize_text(item.get("description") or ""),
        source_type=source_type,
        confidence=confidence,
        needs_review=needs_review,
        user_id=item.get("user_id"),
    )


# ---------------------------------------------------------------------
# Fallback extraction
# ---------------------------------------------------------------------


def extract_merchant_from_text(text_without_amount: str) -> Optional[str]:
    cleaned = clean_merchant_text(text_without_amount)
    cleaned_lower = cleaned.lower()

    if not cleaned:
        return None

    subscription_keywords = [
        "netflix",
        "spotify",
        "youtube",
        "icloud",
        "chatgpt",
        "opencode",
        "gpt",
        "gemini",
        "claude",
        "cursor",
    ]

    for keyword in subscription_keywords:
        if keyword in cleaned_lower:
            # Try to capture phrase containing the keyword.
            words = cleaned.split()
            for i, word in enumerate(words):
                if keyword in word.lower():
                    start = max(0, i - 1)
                    end = min(len(words), i + 3)
                    return title_merchant(" ".join(words[start:end]))

            return title_merchant(keyword)

    for known_merchant in _merchant_category_map:
        if known_merchant.lower() in cleaned_lower:
            return title_merchant(known_merchant)

    generic_patterns = [
        r"\bquán\s+(?:cà phê|coffee|ăn|gần nhà|quen)\b",
        r"\bsiêu thị\b",
        r"\bnhà thuốc\b",
        r"\bcửa hàng\b",
        r"\bshop\b",
    ]

    for pattern in generic_patterns:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            return normalize_text(match.group(0))

    # Proper-noun style merchant: Highlands, Phuc Long, Circle K, etc.
    cap_match = re.search(
        r"\b([A-ZÀ-Ỹ][\wÀ-ỹ]*(?:\s+[A-ZÀ-Ỹ0-9][\wÀ-ỹ]*){0,3})\b",
        cleaned,
    )
    if cap_match:
        candidate = cap_match.group(1).strip()
        if candidate.lower() not in {"cash", "card", "bank", "food", "coffee"}:
            return title_merchant(candidate)

    return None


def extract_simple_fallback(
    text: str,
    usd_rate: Optional[float] = None,
    source_type: str = "text",
) -> Optional[ExtractedTransaction]:
    """Extract one transaction without LLM."""
    text = normalize_text(text)
    if not text:
        return None

    date = extract_date_from_text(text) or today_vietnam()

    amount = None
    original_currency = "VND"

    usd_amount, usd_currency = parse_usd_amount(text, usd_rate)
    if usd_amount is not None:
        amount = usd_amount
        original_currency = usd_currency or "USD"
    else:
        amount = parse_vietnamese_amount(text)

    if amount is None:
        return None

    text_without_amount = remove_amount_from_text(text)
    merchant = extract_merchant_from_text(text_without_amount)

    description = clean_merchant_text(text_without_amount)
    if merchant:
        description = re.sub(re.escape(merchant), " ", description, flags=re.IGNORECASE)
        description = normalize_text(description)

    category = (
        get_category_for_merchant(merchant)
        or get_category_for_keywords(text)
        or "Other"
    )
    payment_method = infer_payment_method(text)

    confidence = 0.75
    needs_review = False

    if amount <= 0:
        needs_review = True
        confidence = 0.4

    if not merchant and category == "Other":
        needs_review = True
        confidence = min(confidence, 0.6)

    return ExtractedTransaction(
        date=date,
        merchant=merchant,
        amount=float(amount),
        currency="VND",
        original_currency=original_currency,
        category=category,
        payment_method=payment_method,
        description=description,
        source_type=source_type,
        confidence=confidence,
        needs_review=needs_review,
    )


def split_possible_transaction_clauses(text: str) -> list[str]:
    """Split text into possible transaction clauses.

    Handles:
    - "30k đánh cầu sân A, 50k đánh cầu sân B"
    - "đánh cầu sân A 30k, đánh cầu sân B 50k"
    """
    text = normalize_text(text)

    # Split by common separators first.
    parts = [
        normalize_text(part)
        for part in re.split(r"\s*(?:,|;|\n|\r|\svà\s)\s*", text, flags=re.IGNORECASE)
        if normalize_text(part)
    ]

    if len(parts) > 1:
        return parts

    # If no separators, split before each amount after the first one.
    amount_pattern = (
        r"(?:\d+\s*tr\s*\d+|\d+(?:[.,]\d+)?\s*(?:k|tr|nghìn|ngàn|triệu|usd|\$))"
    )
    matches = list(re.finditer(amount_pattern, text, flags=re.IGNORECASE))

    if len(matches) <= 1:
        return [text]

    clauses = []
    start = 0

    for index, match in enumerate(matches):
        if index == 0:
            continue

        # Split at previous amount end if structure is "amount description amount description".
        prev_end = matches[index - 1].end()
        clause = normalize_text(text[start:prev_end])
        if clause:
            clauses.append(clause)

        start = prev_end

    last_clause = normalize_text(text[start:])
    if last_clause:
        clauses.append(last_clause)

    return clauses or [text]


def extract_multiple_fallback(
    text: str,
    usd_rate: Optional[float] = None,
    source_type: str = "text",
) -> list[ExtractedTransaction]:
    clauses = split_possible_transaction_clauses(text)

    transactions: list[ExtractedTransaction] = []

    for clause in clauses:
        tx = extract_simple_fallback(clause, usd_rate=usd_rate, source_type=source_type)
        if tx:
            transactions.append(tx)

    # Only treat as multiple fallback if there are actually multiple transactions.
    if len(transactions) <= 1:
        return []

    # Shared date from full input if available.
    shared_date = parse_vietnamese_date(text)
    if shared_date:
        transactions = [
            tx.model_copy(update={"date": shared_date}) for tx in transactions
        ]

    return transactions


# ---------------------------------------------------------------------
# Public extraction functions
# ---------------------------------------------------------------------


async def extract_transaction(
    text: str,
    source_type: str = "text",
    use_fallback: bool = True,
) -> ExtractedTransaction:
    """Extract a single transaction from text."""
    logger.info("Extracting single transaction from text source=%s", source_type)

    if not text or not text.strip():
        raise ExtractionError("Input text is empty")

    resolved_text, resolved_date = resolve_relative_dates(text)

    try:
        response_text = await call_llm(resolved_text, multiple=False)
        data = extract_json_from_llm_response(response_text)

        if isinstance(data, list):
            if not data:
                raise ExtractionError("LLM returned empty transaction list")

            # If LLM returns multiple despite single mode, take first but mark review.
            first = data[0]
            first["needs_review"] = True
            first["confidence"] = min(float(first.get("confidence", 0.7)), 0.7)
            data = first

        if not isinstance(data, dict):
            raise ExtractionError("LLM returned invalid transaction payload")

        return normalize_transaction_payload(
            data,
            source_type=source_type,
            resolved_date=resolved_date,
            original_text=resolved_text,
        )

    except Exception as exc:
        logger.warning("LLM single extraction failed: %s", exc)

        if not use_fallback:
            raise ExtractionError(str(exc)) from exc

        usd_rate = await get_usd_to_vnd_rate()
        fallback = extract_simple_fallback(
            resolved_text,
            usd_rate=usd_rate,
            source_type=source_type,
        )

        if fallback:
            return fallback

        raise ExtractionError(
            "Failed to extract transaction with both LLM and fallback"
        ) from exc


async def extract_transactions(
    text: str,
    source_type: str = "text",
    use_fallback: bool = True,
) -> list[ExtractedTransaction]:
    """Extract one or more transactions from text."""
    logger.info("Extracting multiple transactions from text source=%s", source_type)

    if not text or not text.strip():
        return []

    resolved_text, resolved_date = resolve_relative_dates(text)

    try:
        response_text = await call_llm(resolved_text, multiple=True)
        data = extract_json_from_llm_response(response_text)

        if isinstance(data, dict):
            data = [data]

        if not isinstance(data, list):
            raise ExtractionError("LLM returned invalid transaction list payload")

        transactions = []

        for item in data:
            if not isinstance(item, dict):
                continue

            try:
                tx = normalize_transaction_payload(
                    item,
                    source_type=source_type,
                    resolved_date=resolved_date,
                    original_text=resolved_text,
                )
                transactions.append(tx)
            except Exception as item_exc:
                logger.warning(
                    "Failed to normalize transaction item=%s error=%s", item, item_exc
                )

        if transactions:
            return transactions

        raise ExtractionError("LLM returned no valid transactions")

    except Exception as exc:
        logger.warning("LLM multiple extraction failed: %s", exc)

        if not use_fallback:
            return []

        usd_rate = await get_usd_to_vnd_rate()

        multiple = extract_multiple_fallback(
            resolved_text,
            usd_rate=usd_rate,
            source_type=source_type,
        )
        if multiple:
            return multiple

        single = extract_simple_fallback(
            resolved_text,
            usd_rate=usd_rate,
            source_type=source_type,
        )
        return [single] if single else []


# ---------------------------------------------------------------------
# Convenience sync-safe helpers for tests
# ---------------------------------------------------------------------


def extract_simple_for_test(
    text: str, usd_rate: float = USD_TO_VND_RATE
) -> Optional[ExtractedTransaction]:
    """Deterministic extraction helper for unit tests."""
    return extract_simple_fallback(text, usd_rate=usd_rate)


def extract_multiple_for_test(
    text: str, usd_rate: float = USD_TO_VND_RATE
) -> list[ExtractedTransaction]:
    """Deterministic multiple extraction helper for unit tests."""
    return extract_multiple_fallback(text, usd_rate=usd_rate)
