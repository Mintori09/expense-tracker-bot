# Finance Automation Bot

A Telegram bot that automates personal finance tracking by extracting expense data from text, images, and PDFs.

## Features

- **Text Input**: Send expense text like "Ăn trưa 85k ở Phở Thìn"
- **Image OCR**: Upload receipt photos for automatic extraction
- **PDF Support**: Process PDF invoices
- **Data Storage**: SQLite database + Excel export
- **Monthly Summaries**: View spending by category

## Setup

### Prerequisites

1. Python 3.11+
2. Telegram Bot Token (create via @BotFather)
3. Ollama (optional, for LLM extraction)
4. Tesseract OCR with Vietnamese language pack

### Installation with Nix (Recommended)

```bash
# Enter development shell
nix develop

# Install Python dependencies
pip install -r requirements.txt

# Run the bot
python -m app.main
```

### Installation without Nix

```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get install tesseract-ocr tesseract-ocr-vie poppler-utils

# Install Python dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your bot token

# Run
python -m app.main
```

Or on Arch Linux:

```bash
sudo pacman -S tesseract tesseract-data-vie poppler
pip install -r requirements.txt
```

### Environment Variables

| Variable             | Description                              | Default                    |
| -------------------- | ---------------------------------------- | -------------------------- |
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token                  | Required                   |
| `LLM_PROVIDER`       | LLM provider: "ollama" or "google"       | ollama                     |
| `LLM_API_KEY`        | API key for LLM (use "ollama" for local) | ollama                     |
| `LLM_BASE_URL`       | LLM API endpoint                         | http://localhost:11434/v1  |
| `LLM_MODEL`          | LLM model name                           | gemma3:4b-it-qat           |
| `SQLITE_PATH`        | SQLite database path                     | data/finance/expenses.db   |
| `EXCEL_PATH`         | Excel export path                        | data/finance/expenses.xlsx |

## Usage

### Start the bot

```bash
python -m app.main
```

### Commands

- `/start` - Show welcome message
- `/help` - Show usage instructions
- `/month` - Show monthly spending summary
- `/today` - Show today's expenses
- `/week` - Show this week's expenses
- `/7days` - Show last 7 days expenses (can use any number like `/14days`, `/30days`)
- `/export` - Export all transactions to Excel (sends file)
- `/export today|week|month|year` - Export by period
- `/review` - Show transactions needing review
- `/edit` - Edit pending transaction
- `/remove <id>` - Remove a transaction
- `/getId` - Get current chat ID

### Text Format

Send any of these formats:

- `Ăn trưa 85k ở Phở Thìn`
- `cà phê 55k tại The Coffee House`
- `GrabBike 45k`
- `2.5tr internet VNPT`

### Vietnamese Relative Date Support

The bot understands relative date expressions:

- `Ăn trưa hôm qua 85k` → yesterday's date
- `Coffee ngày mai 55k` → tomorrow's date
- `Ăn tối hôm kia 120k` → day before yesterday
- `Ăn trưa ngày này tháng trước 85k` → same day last month
- `Coffee ngày này tuần trước 55k` → same weekday last week
- `Ăn tối ngày này năm trước 120k` → same day last year

### Image/PDF

Simply send a photo or PDF document containing receipt/invoice text.

## Project Structure

```
telegram-bot/
├── app/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── config.py            # Configuration management
│   ├── bot/
│   │   ├── __init__.py
│   │   └── dispatcher.py    # Telegram application setup
│   ├── core/
│   │   ├── __init__.py
│   │   ├── database.py      # SQLite database operations
│   │   └── logging.py       # Logging setup
│   ├── modules/
│   │   ├── __init__.py
│   │   └── finance/
│   │       ├── __init__.py
│   │       ├── handlers.py  # Telegram handlers
│   │       ├── service.py   # Business logic
│   │       ├── repository.py # Database operations
│   │       ├── extractor.py  # Transaction extraction
│   │       ├── ocr.py         # Image/PDF processing
│   │       ├── storage.py     # Excel export
│   │       ├── models.py      # Data models
│   │       └── constants.py   # Module constants
│   └── shared/
│       ├── __init__.py
│       ├── constants.py     # Shared constants
│       └── exceptions.py    # Shared exceptions
├── tests/
│   └── modules/
│       └── finance/         # Finance module tests
├── data/
│   └── finance/             # Runtime data (db, excel)
├── logs/                    # Log files
├── Dockerfile
└── README.md
```

## Development

### Run tests

```bash
pytest tests/ -v
```

### Docker deployment

Using docker-compose (recommended - includes Ollama):

```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your bot token

# Start the bot and Ollama
docker-compose up -d

# Initial setup: pull the model in Ollama
docker exec -it ollama ollama pull gemma3:4b-it-qat
```

Or using docker directly:

```bash
docker build -t finance-bot .
docker run -d --env-file .env -v $(pwd)/data:/app/data/finance finance-bot
```

### Using Nix

```bash
# Enter development shell
nix develop

# Run the bot
python -m app.main
```

## License

MIT
