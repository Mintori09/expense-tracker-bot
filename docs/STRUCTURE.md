# Project Structure

This document describes the architecture of the Telegram Bot System after refactoring.

## Architecture Overview

```
Telegram Bot System
├── Core system (app/core)
├── Bot interface (app/bot)
├── Shared utilities (app/shared)
└── Business modules (app/modules)
    └── Finance module (app/modules/finance)
```

## Layer Responsibilities

### Core Layer (`app/core/`)

Infrastructure components that can be used by any module:

- `database.py` - SQLite connection, schema, and basic operations
- `logging.py` - Application logging configuration

### Bot Layer (`app/bot/`)

Telegram-specific interface:

- `dispatcher.py` - Create Application, register handlers
- No business logic should be here

### Module Layer (`app/modules/`)

Business domain logic:

- `finance/` - Expense tracking module
  - `handlers.py` - Telegram message handlers
  - `service.py` - Business logic coordination
  - `repository.py` - Database operations
  - `extractor.py` - Text extraction
  - `ocr.py` - Image/PDF processing
  - `storage.py` - Excel export
  - `models.py` - Data models
  - `constants.py` - Module constants

### Shared Layer (`app/shared/`)

Common utilities used across modules:

- `constants.py` - Shared constants
- `exceptions.py` - Common exceptions

## Dependency Direction

```
app.main
  ↓
app.bot
  ↓
app.modules.finance
  ↓
app.core / app.shared
```

Core must never import from finance. Finance can import from core and shared.
