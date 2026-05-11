"""
Vietnamese date utilities for transaction extraction.

Supports:
- Relative Vietnamese dates:
  hôm nay, hôm qua, hôm kia, ngày mai, mai, hôm sau, ngày mốt, mốt
- Offset dates:
  2 ngày nữa, 3 hôm sau, 4 bữa trước
- Week expressions:
  tuần này, tuần sau, tuần trước, đầu tuần sau, cuối tuần này
- Weekdays:
  thứ 2, thứ hai, thứ 3 tuần sau, chủ nhật tuần trước
- Absolute dates:
  12/05, 12/05/2026, 12-05-26
  ngày 12 tháng 5, ngày 12 tháng 5 năm 2026

Public API:
- parse_vietnamese_date(text, base=None) -> Optional[str]
- resolve_relative_dates(text, base=None) -> tuple[str, Optional[str]]
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


WEEKDAY_MAP = {
    "thứ 2": 0,
    "thứ hai": 0,
    "t2": 0,
    "monday": 0,
    "thứ 3": 1,
    "thứ ba": 1,
    "t3": 1,
    "tuesday": 1,
    "thứ 4": 2,
    "thứ tư": 2,
    "t4": 2,
    "wednesday": 2,
    "thứ 5": 3,
    "thứ năm": 3,
    "t5": 3,
    "thursday": 3,
    "thứ 6": 4,
    "thứ sáu": 4,
    "t6": 4,
    "friday": 4,
    "thứ 7": 5,
    "thứ bảy": 5,
    "t7": 5,
    "saturday": 5,
    "chủ nhật": 6,
    "chu nhat": 6,
    "cn": 6,
    "sunday": 6,
}


def now_vietnam() -> datetime:
    """Return current datetime in Vietnam timezone."""
    return datetime.now(VIETNAM_TZ)


def today_vietnam() -> str:
    """Return today's date in Vietnam timezone as YYYY-MM-DD."""
    return format_date(now_vietnam())


def normalize_spaces(text: str) -> str:
    """Normalize repeated whitespace."""
    return re.sub(r"\s+", " ", text or "").strip()


def format_date(dt: datetime) -> str:
    """Format datetime as YYYY-MM-DD."""
    return dt.strftime("%Y-%m-%d")


def ensure_tz(dt: datetime) -> datetime:
    """Ensure datetime has Vietnam timezone."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=VIETNAM_TZ)
    return dt.astimezone(VIETNAM_TZ)


def normalize_year(year_raw: Optional[str], base_year: int) -> int:
    """Normalize year string.

    - None -> base_year
    - 26 -> 2026
    - 2026 -> 2026
    """
    if not year_raw:
        return base_year

    year = int(year_raw)
    if year < 100:
        year += 2000

    return year


def safe_date(year: int, month: int, day: int) -> Optional[str]:
    """Build date safely. Return None if invalid."""
    try:
        return format_date(datetime(year, month, day, tzinfo=VIETNAM_TZ))
    except ValueError:
        return None


def next_weekday(
    base: datetime,
    target_weekday: int,
    include_today: bool = True,
) -> datetime:
    """Return next occurrence of target weekday.

    Monday = 0, Sunday = 6.

    If include_today=True and base already matches target weekday,
    returns base.
    """
    base = ensure_tz(base)
    days_ahead = target_weekday - base.weekday()

    if days_ahead < 0:
        days_ahead += 7

    if days_ahead == 0 and not include_today:
        days_ahead = 7

    return base + timedelta(days=days_ahead)


def previous_weekday(
    base: datetime,
    target_weekday: int,
    include_today: bool = False,
) -> datetime:
    """Return previous occurrence of target weekday.

    Monday = 0, Sunday = 6.
    """
    base = ensure_tz(base)
    days_back = base.weekday() - target_weekday

    if days_back < 0:
        days_back += 7

    if days_back == 0 and not include_today:
        days_back = 7

    return base - timedelta(days=days_back)


def start_of_week(base: datetime) -> datetime:
    """Return Monday of the week containing base."""
    base = ensure_tz(base)
    return base - timedelta(days=base.weekday())


def parse_absolute_vietnamese_date(
    text: str,
    base: Optional[datetime] = None,
) -> Optional[str]:
    """Parse absolute Vietnamese date formats.

    Supported:
    - 12/05
    - 12/05/2026
    - 12-05-26
    - ngày 12 tháng 5
    - ngày 12 tháng 5 năm 2026
    """
    if not text:
        return None

    base = ensure_tz(base or now_vietnam())
    text_lower = normalize_spaces(text.lower())

    # 12/05, 12/05/2026, 12-05-26
    slash_match = re.search(
        r"\b(\d{1,2})\s*[/-]\s*(\d{1,2})(?:\s*[/-]\s*(\d{2,4}))?\b",
        text_lower,
    )
    if slash_match:
        day = int(slash_match.group(1))
        month = int(slash_match.group(2))
        year = normalize_year(slash_match.group(3), base.year)
        return safe_date(year, month, day)

    # ngày 12 tháng 5, ngày 12 tháng 5 năm 2026
    vietnamese_match = re.search(
        r"\bngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})(?:\s+năm\s+(\d{2,4}))?\b",
        text_lower,
    )
    if vietnamese_match:
        day = int(vietnamese_match.group(1))
        month = int(vietnamese_match.group(2))
        year = normalize_year(vietnamese_match.group(3), base.year)
        return safe_date(year, month, day)

    return None


def parse_basic_relative_date(
    text: str,
    base: datetime,
) -> Optional[str]:
    """Parse simple fixed relative expressions."""
    text_lower = normalize_spaces(text.lower())

    rules = [
        # Today.
        (r"\b(hôm nay|bữa nay|nay|today)\b", 0),
        # Past.
        (r"\b(hôm qua|bữa qua|yesterday)\b", -1),
        (r"\b(hôm kia|bữa kia)\b", -2),
        # Future.
        (r"\b(mống mai|mồng mai|mong mai)\b", 2),
        (r"\b(ngày mai|mai|tomorrow)\b", 1),
        (r"\b(ngày mốt|mốt)\b", 2),
        # Conversational next day.
        (r"\b(ngày hôm sau|hôm sau|bữa sau)\b", 1),
    ]

    for pattern, offset_days in rules:
        if re.search(pattern, text_lower):
            return format_date(base + timedelta(days=offset_days))

    return None


def parse_offset_relative_date(
    text: str,
    base: datetime,
) -> Optional[str]:
    """Parse expressions like 2 ngày nữa, 3 hôm trước."""
    text_lower = normalize_spaces(text.lower())

    # 2 ngày nữa, 3 hôm sau, 4 bữa tới
    future_match = re.search(
        r"\b(\d+)\s*(ngày|hôm|bữa)\s*(nữa|sau|tới|sắp tới)\b",
        text_lower,
    )
    if future_match:
        days = int(future_match.group(1))
        return format_date(base + timedelta(days=days))

    # 2 ngày trước, 3 hôm trước, 4 bữa trước
    past_match = re.search(
        r"\b(\d+)\s*(ngày|hôm|bữa)\s*trước\b",
        text_lower,
    )
    if past_match:
        days = int(past_match.group(1))
        return format_date(base - timedelta(days=days))

    # N tuần nữa / N tuần sau
    future_week_match = re.search(
        r"\b(\d+)\s*tuần\s*(nữa|sau|tới)\b",
        text_lower,
    )
    if future_week_match:
        weeks = int(future_week_match.group(1))
        return format_date(base + timedelta(days=weeks * 7))

    # N tuần trước
    past_week_match = re.search(
        r"\b(\d+)\s*tuần\s*trước\b",
        text_lower,
    )
    if past_week_match:
        weeks = int(past_week_match.group(1))
        return format_date(base - timedelta(days=weeks * 7))

    if re.search(r"\bngày này tuần trước\b", text_lower):
        return format_date(base - timedelta(days=7))

    if re.search(r"\bngày này tháng trước\b", text_lower):
        year = base.year
        month = base.month - 1
        if month == 0:
            month = 12
            year -= 1

        day = min(base.day, _days_in_month(year, month))
        return safe_date(year, month, day)

    if re.search(r"\bngày này năm trước\b", text_lower):
        year = base.year - 1
        day = min(base.day, _days_in_month(year, base.month))
        return safe_date(year, base.month, day)

    return None


def _days_in_month(year: int, month: int) -> int:
    """Return number of days in the given month."""
    if month == 12:
        next_month = datetime(year + 1, 1, 1, tzinfo=VIETNAM_TZ)
    else:
        next_month = datetime(year, month + 1, 1, tzinfo=VIETNAM_TZ)
    this_month = datetime(year, month, 1, tzinfo=VIETNAM_TZ)
    return (next_month - this_month).days


def parse_week_expression(
    text: str,
    base: datetime,
) -> Optional[str]:
    """Parse week-level expressions.

    Default choices:
    - tuần này -> today
    - tuần sau -> same weekday next week
    - tuần trước -> same weekday previous week
    - đầu tuần -> Monday
    - cuối tuần -> Saturday
    """
    text_lower = normalize_spaces(text.lower())

    monday_this_week = start_of_week(base)
    saturday_this_week = monday_this_week + timedelta(days=5)

    if re.search(r"\b(tuần này|this week)\b", text_lower):
        return format_date(base)

    if re.search(r"\b(tuần sau|tuần tới|next week)\b", text_lower):
        return format_date(base + timedelta(days=7))

    if re.search(r"\b(tuần trước|last week)\b", text_lower):
        return format_date(base - timedelta(days=7))

    if re.search(r"\b(đầu tuần này|đầu tuần)\b", text_lower):
        return format_date(monday_this_week)

    if re.search(r"\bđầu tuần sau\b", text_lower):
        return format_date(monday_this_week + timedelta(days=7))

    if re.search(r"\bđầu tuần trước\b", text_lower):
        return format_date(monday_this_week - timedelta(days=7))

    if re.search(r"\bcuối tuần này\b", text_lower):
        return format_date(saturday_this_week)

    if re.search(r"\bcuối tuần sau\b", text_lower):
        return format_date(saturday_this_week + timedelta(days=7))

    if re.search(r"\bcuối tuần trước\b", text_lower):
        return format_date(saturday_this_week - timedelta(days=7))

    # If user only says "cuối tuần", default to upcoming Saturday.
    if re.search(r"\bcuối tuần\b", text_lower):
        return format_date(next_weekday(base, 5, include_today=True))

    return None


def parse_weekday_expression(
    text: str,
    base: datetime,
) -> Optional[str]:
    """Parse weekday expressions.

    Supported:
    - thứ 2
    - thứ hai
    - thứ 6 tuần sau
    - chủ nhật tuần trước
    """
    text_lower = normalize_spaces(text.lower())

    # Match longer weekday names first to avoid partial collisions.
    weekday_items = sorted(
        WEEKDAY_MAP.items(), key=lambda item: len(item[0]), reverse=True
    )

    for weekday_text, weekday_index in weekday_items:
        if not re.search(rf"\b{re.escape(weekday_text)}\b", text_lower):
            continue

        monday_this_week = start_of_week(base)

        if re.search(r"\b(tuần sau|tuần tới|next week)\b", text_lower):
            target = monday_this_week + timedelta(days=7 + weekday_index)
            return format_date(target)

        if re.search(r"\b(tuần trước|last week)\b", text_lower):
            target = (
                monday_this_week - timedelta(days=7) + timedelta(days=weekday_index)
            )
            return format_date(target)

        if re.search(r"\b(tuần này|this week)\b", text_lower):
            target = monday_this_week + timedelta(days=weekday_index)
            return format_date(target)

        # Default: upcoming occurrence, including today.
        return format_date(next_weekday(base, weekday_index, include_today=True))

    return None


def parse_vietnamese_relative_date(
    text: str,
    base: Optional[datetime] = None,
) -> Optional[str]:
    """Parse Vietnamese relative or absolute date from text.

    Priority:
    1. Absolute date
    2. Basic relative date
    3. Offset relative date
    4. Weekday expression
    5. Week expression
    """
    if not text:
        return None

    base = ensure_tz(base or now_vietnam())

    absolute = parse_absolute_vietnamese_date(text, base=base)
    if absolute:
        return absolute

    basic = parse_basic_relative_date(text, base=base)
    if basic:
        return basic

    offset = parse_offset_relative_date(text, base=base)
    if offset:
        return offset

    # Weekday should run before general week expression:
    # "thứ 2 tuần sau" should return Monday next week,
    # not merely same weekday + 7 days.
    weekday = parse_weekday_expression(text, base=base)
    if weekday:
        return weekday

    week = parse_week_expression(text, base=base)
    if week:
        return week

    return None


def parse_vietnamese_date(
    text: str,
    base: Optional[datetime] = None,
) -> Optional[str]:
    """Public date parser for transaction extraction."""
    return parse_vietnamese_relative_date(text, base=base)


def resolve_relative_dates(
    text: str,
    base: Optional[datetime] = None,
) -> Tuple[str, Optional[str]]:
    """Resolve Vietnamese relative date in text.

    Kept compatible with existing extraction code.

    Returns:
        tuple:
            - original text
            - resolved date as YYYY-MM-DD, or None
    """
    resolved_date = parse_vietnamese_relative_date(text, base=base)
    if not resolved_date:
        return text, None

    text_lower = normalize_spaces(text.lower())
    patterns = [
        r"\b(hôm nay|bữa nay|nay|today)\b",
        r"\b(hôm qua|bữa qua|yesterday)\b",
        r"\b(hôm kia|bữa kia)\b",
        r"\b(ngày mai|mai|tomorrow)\b",
        r"\b(mống mai|mồng mai|mong mai)\b",
        r"\b(ngày mốt|mốt)\b",
        r"\b(ngày hôm sau|hôm sau|bữa sau)\b",
        r"\b(\d+)\s*(ngày|hôm|bữa)\s*(nữa|sau|tới|sắp tới)\b",
        r"\b(\d+)\s*(ngày|hôm|bữa)\s*trước\b",
        r"\b(\d+)\s*tuần\s*(nữa|sau|tới)\b",
        r"\b(\d+)\s*tuần\s*trước\b",
        r"\b(ngày này tuần trước|ngày này tháng trước|ngày này năm trước)\b",
        r"\b(thứ\s*[2-7]|thứ\s+(hai|ba|tư|năm|sáu|bảy)|chủ nhật|cn)\b(?:\s*(tuần này|tuần sau|tuần tới|tuần trước))?",
        r"\b(tuần này|tuần sau|tuần tới|tuần trước|đầu tuần này|đầu tuần sau|đầu tuần trước|đầu tuần|cuối tuần này|cuối tuần sau|cuối tuần trước|cuối tuần)\b",
    ]

    replaced_text = text
    for pattern in patterns:
        if re.search(pattern, text_lower, flags=re.IGNORECASE):
            replaced_text = re.sub(
                pattern,
                resolved_date,
                replaced_text,
                count=1,
                flags=re.IGNORECASE,
            )
            break

    return normalize_spaces(replaced_text), resolved_date


def extract_date_from_text(
    text: str,
    base: Optional[datetime] = None,
) -> Optional[str]:
    """Extract date from free text.

    Priority:
    1. Explicit absolute dates (YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, ...)
    2. Vietnamese relative dates
    """
    if not text:
        return None

    base = ensure_tz(base or now_vietnam())
    text_lower = normalize_spaces(text.lower())

    # 2025-01-15 or 2025/01/15
    iso_match = re.search(r"\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b", text_lower)
    if iso_match:
        year = int(iso_match.group(1))
        month = int(iso_match.group(2))
        day = int(iso_match.group(3))
        return safe_date(year, month, day)

    absolute = parse_absolute_vietnamese_date(text_lower, base=base)
    if absolute:
        return absolute

    return parse_vietnamese_relative_date(text_lower, base=base)


def replace_relative_date_with_absolute(
    text: str,
    base: Optional[datetime] = None,
) -> Tuple[str, Optional[str]]:
    """Optional helper: append resolved date into text for LLM clarity.

    Example:
        "hôm qua ăn phở 40k"
        -> "hôm qua ăn phở 40k (resolved_date: 2026-05-10)"

    Returns:
        tuple:
            - enriched text
            - resolved date
    """
    resolved_date = parse_vietnamese_relative_date(text, base=base)

    if not resolved_date:
        return text, None

    enriched = f"{text} (resolved_date: {resolved_date})"
    return enriched, resolved_date
