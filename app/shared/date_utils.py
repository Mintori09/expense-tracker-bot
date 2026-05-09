"""Vietnamese date parsing utilities for relative date expressions."""

import logging
import re
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Vietnamese relative date patterns and their offsets
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
    
    for pattern, offset in COMPILED_PATTERNS:
        match = pattern.search(text)
        if match:
            target_date = today + timedelta(days=offset)
            date_str = target_date.strftime("%Y-%m-%d")
            logger.info(f"Parsed '{match.group(1)}' as {date_str}")
            return date_str
    
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