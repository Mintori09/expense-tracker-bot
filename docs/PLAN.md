# Refactor Plan

This document outlines the refactoring of the Telegram Bot from a monolithic structure to a modular architecture.

## Target Architecture

```
telegram-bot/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── bot/
│   │   ├── __init__.py
│   │   └── dispatcher.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   └── logging.py
│   ├── modules/
│   │   ├── __init__.py
│   │   └── finance/
│   │       ├── __init__.py
│   │       ├── handlers.py
│   │       ├── service.py
│   │       ├── repository.py
│   │       ├── extractor.py
│   │       ├── ocr.py
│   │       ├── storage.py
│   │       ├── models.py
│   │       └── constants.py
│   └── shared/
│       ├── __init__.py
│       ├── constants.py
│       └── exceptions.py
├── tests/
│   └── modules/
│       └── finance/
├── data/
│   └── finance/
├── logs/
└── docs/
```

## Module Responsibilities

### app/main.py

- Bootstrap application
- Setup logging
- Initialize database
- Start Telegram bot

### app/bot/dispatcher.py

- Create Telegram Application
- Register module handlers

### app/core/

- Database connection
- Logging setup
- Shared utilities

### app/modules/finance/

- Transaction extraction
- OCR processing
- Excel storage
- Telegram handlers

### app/shared/

- Common exceptions
- Shared constants
