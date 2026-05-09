# Plan: Vietnamese Relative Date Parsing

## Context

The finance bot currently extracts dates from user input, but only handles explicit dates like "2025-01-15" from LLM extraction. Users want to use natural Vietnamese expressions like:
- "hôm qua" (yesterday)
- "hôm kia" (day before yesterday)  
- "ngày mai" (tomorrow)
- "mống mai" (the day after tomorrow)
- "tháng sau" (next month)

These expressions need to be converted to actual dates (YYYY-MM-DD format) for proper transaction tracking.

## Approach

Create a new utility module `app/shared/date_utils.py` with a function `parse_vietnamese_date()` that:
1. Detects relative date expressions in Vietnamese text
2. Converts them to actual calendar dates based on the current date
3. Returns the date in YYYY-MM-DD format

The function will be integrated into the extraction flow by pre-processing the input text to replace Vietnamese relative date expressions with actual dates before passing to the LLM. This benefits both LLM-based and fallback extraction.

## Files to Modify

1. **New file**: `app/shared/date_utils.py` - Core date parsing logic
2. **New file**: `tests/shared/test_date_utils.py` - Unit tests for date parsing
3. **Modified**: `app/modules/finance/extractor.py` - Pre-process text to resolve relative dates before LLM extraction
4. **Modified**: `app/shared/__init__.py` - Export new date utility functions

## Reuse

- Use existing `datetime` imports already present in the codebase (`from datetime import datetime`)
- Follow the same logging pattern using `logger = logging.getLogger(__name__)`
- Follow the module structure pattern from `app/shared/constants.py`

## Implementation Details

### Vietnamese Date Expressions to Support

| Expression | Meaning | Offset |
|------------|---------|--------|
| hôm qua | yesterday | -1 day |
| hôm kia | day before yesterday | -2 days |
| ngày mai | tomorrow | +1 day |
| mống mai | day after tomorrow | +2 days |
| nữa | later/today (context dependent) | today |
| hôm nay | today | 0 days |

### Text Pre-processing Strategy

In `extract_transaction()`:
1. First, scan input text for Vietnamese relative date expressions
2. Replace them with the actual date (YYYY-MM-DD format)
3. Pass the modified text to LLM for extraction
4. This way, the LLM receives "Ăn trưa 2025-01-15 85k" instead of "Ăn trưa hôm qua 85k"

For fallback extraction, the same pre-processing is applied.

## Steps

- [ ] Create `app/shared/date_utils.py` with `parse_vietnamese_date()` and `resolve_relative_dates()` functions
- [ ] Update `app/shared/__init__.py` to export date utilities
- [ ] Create `tests/shared/test_date_utils.py` with unit tests
- [ ] Modify `extract_transaction()` to pre-process text with resolved dates
- [ ] Modify `extract_transactions()` (multi-transaction) to pre-process text
- [ ] Modify `extract_simple_fallback()` to support relative date expressions
- [ ] Modify `extract_multiple_fallback()` to support relative date expressions
- [ ] Test with Vietnamese expressions like "Ăn trưa hôm qua 85k"

## Verification

1. Run unit tests: `pytest tests/shared/test_date_utils.py -v`
2. Run all tests: `pytest tests/ -v`
3. Manual testing via Telegram with messages like:
   - "Ăn trưa hôm qua 85k ở Phở Thìn" → should extract date as yesterday
   - "Coffee 55k ngày mai tại The Coffee House" → should extract date as tomorrow
   - "GrabBike 45k hôm kia" → should extract date as day before yesterday