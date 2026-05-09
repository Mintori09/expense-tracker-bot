"""Vietnamese date parsing utilities for relative date expressions."""

import calendar
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Vietnamese relative date patterns and their offsets (simple day offsets)
VIETNAMESE_DATE_PATTERNS = {
    # Yesterday variations
    r"\b(hôm qua)\b": -1,
    # Day before yesterday
    r"\b(hôm kia)\b": -2,
    # Tomorrow variations
    r"\b(ngày mai)\b": 1,
    r"\b(mống mai|mống mai)\b": 2,
    # Today
    r"\b(hôm nay|nay)\b": 0,
}

# Compile patterns for efficiency
COMPILED_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE), offset)
    for pattern, offset in VIETNAMESE_DATE_PATTERNS.items()
]


def parse_vietnamese_date(text: str) -> Optional[str]:
    """Parse Vietnamese relative date expression and return actual date.
    
    Args:
        text: Text containing Vietnamese date expression like "hôm qua", "ngày mai"
        
    Returns:
        Date in YYYY-MM-DD format, or None if no relative date found
        
    Examples:
        >>> parse_vietnamese_date("Ăn trưa hôm qua 85k")
        "2025-01-15"  # if today is 2025-01-16
        >>> parse_vietnamese_date("Coffee ngày mai")
        "2025-01-17"  # if today is 2025-01-16
    """
    today = datetime.now().date()
    
    # First check for complex patterns (month/year offsets)
    complex_result = parse_complex_vietnamese_date(text)
    if complex_result:
        return complex_result
    
    for pattern, offset in COMPILED_PATTERNS:
        match = pattern.search(text)
        if match:
            target_date = today + timedelta(days=offset)
            date_str = target_date.strftime("%Y-%m-%d")
            logger.info(f"Parsed '{match.group(1)}' as {date_str}")
            return date_str
    
    return None


def parse_complex_vietnamese_date(text: str) -> Optional[str]:
    """Parse complex Vietnamese date expressions like 'ngày này tháng trước'.
    
    Patterns supported:
    - ngày này tháng trước: same day of last month
    - ngày này tuần trước: same weekday of last week  
    - ngày này năm trước: same day of last year
    
    Args:
        text: Text containing complex Vietnamese date expression
        
    Returns:
        Date in YYYY-MM-DD format, or None if no match
    """
    today = datetime.now()
    
    # Pattern: "ngày này tháng trước" - same day of last month
    match = re.search(r"\bngày này tháng trước\b", text, re.IGNORECASE)
    if match:
        year = today.year
        month = today.month - 1
        if month == 0:
            month = 12
            year -= 1
        # Handle case where last month doesn't have the same day
        day = min(today.day, calendar.monthrange(year, month)[1])
        result = datetime(year, month, day).strftime("%Y-%m-%d")
        logger.info(f"Parsed 'ngày này tháng trước' as {result}")
        return result
    
    # Pattern: "ngày này tuần trước" - same weekday of last week
    match = re.search(r"\bngày này tuần trước\b", text, re.IGNORECASE)
    if match:
        target = today - timedelta(weeks=1)
        result = target.strftime("%Y-%m-%d")
        logger.info(f"Parsed 'ngày này tuần trước' as {result}")
        return result
    
    # Pattern: "ngày này năm trước" - same day of last year
    match = re.search(r"\bngày này năm trước\b", text, re.IGNORECASE)
    if match:
        year = today.year - 1
        month = today.month
        day = today.day
        # Handle Feb 29 case for non-leap years
        try:
            result = datetime(year, month, day).strftime("%Y-%m-%d")
            logger.info(f"Parsed 'ngày này năm trước' as {result}")
            return result
        except ValueError:
            # Feb 29 -> Feb 28 in non-leap year
            result = datetime(year, month, day - 1).strftime("%Y-%m-%d")
            logger.info(f"Parsed 'ngày này năm trước' as {result} (adjusted from Feb 29)")
            return result
    
    return None


def resolve_relative_dates(text: str) -> tuple[str, Optional[str]]:
    """Resolve Vietnamese relative dates in text to actual dates.
    
    This function finds Vietnamese relative date expressions in the text
    and replaces them with the actual date (YYYY-MM-DD format), making it
    easier for LLM or other processing to handle.
    
    Args:
        text: Input text potentially containing Vietnamese relative date expressions
        
    Returns:
        Tuple of (modified_text, resolved_date_str) where:
        - modified_text has relative dates replaced with actual dates
        - resolved_date_str is the resolved date if found, None otherwise
        
    Examples:
        >>> resolve_relative_dates("Ăn trưa hôm qua 85k")
        ("Ăn trưa 2025-01-15 85k", "2025-01-15")
    """
    today = datetime.now().date()
    modified_text = text
    resolved_date = None
    
    # First check for complex patterns (month/year offsets)
    complex_result = parse_complex_vietnamese_date(text)
    if complex_result:
        # Try to find and replace the complex pattern in text
        complex_patterns = [
            (r"\bngày này tháng trước\b", "ngày này tháng trước"),
            (r"\bngày này tuần trước\b", "ngày này tuần trước"),
            (r"\bngày này năm trước\b", "ngày này năm trước"),
        ]
        for pattern, phrase in complex_patterns:
            match = re.search(pattern, modified_text, re.IGNORECASE)
            if match:
                modified_text = modified_text[:match.start()] + complex_result + modified_text[match.end():]
                resolved_date = complex_result
                logger.info(f"Resolved '{phrase}' to {complex_result} in text")
                break
        if resolved_date:
            return modified_text, resolved_date
    
    for pattern, offset in COMPILED_PATTERNS:
        match = pattern.search(modified_text)
        if match:
            target_date = today + timedelta(days=offset)
            date_str = target_date.strftime("%Y-%m-%d")
            
            # Replace the matched expression with the actual date
            modified_text = modified_text[:match.start()] + date_str + modified_text[match.end():]
            resolved_date = date_str
            
            logger.info(f"Resolved '{match.group(1)}' to {date_str} in text")
            break  # Only resolve the first match
    
    return modified_text, resolved_date


def extract_date_from_text(text: str) -> Optional[str]:
    """Extract date from text, supporting both absolute and relative Vietnamese dates.
    
    Args:
        text: Input text to extract date from
        
    Returns:
        Date in YYYY-MM-DD format if found, None otherwise
    """
    # First try absolute date patterns (YYYY-MM-DD or DD/MM/YYYY)
    absolute_pattern = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
    match = absolute_pattern.search(text)
    if match:
        return match.group(1)
    
    # Also try DD/MM/YYYY format
    vietnam_date_pattern = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")
    match = vietnam_date_pattern.search(text)
    if match:
        try:
            date_obj = datetime.strptime(match.group(1), "%d/%m/%Y")
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            pass
    
    # Finally try Vietnamese relative dates
    return parse_vietnamese_date(text)