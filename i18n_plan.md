# Multi-language Feature Plan

## Context
User wants to add English and Vietnamese language support for the Telegram finance bot.

## Approach
1. Create i18n module with translation files
2. Store user's preferred language in database
3. Update all messages to use translation keys
4. Add `/language` command to switch languages

## Files to Create/Modify
- `app/i18n/en.py` - English translations
- `app/i18n/vi.py` - Vietnamese translations  
- `app/i18n/__init__.py` - i18n helper functions
- `app/core/database.py` - Add `user_language` column
- `app/modules/finance/handlers.py` - Update messages to use i18n
- `app/modules/finance/service.py` - Update messages to use i18n

## Implementation Steps
- [ ] Create i18n translation files
- [ ] Update database schema for user language preference
- [ ] Add `/language` command
- [ ] Replace hardcoded messages with i18n calls
- [ ] Test both languages

## Verification
- Run all tests
- Test `/language en` and `/language vi`
- Test command responses show correct language