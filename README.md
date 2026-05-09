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
python main.py
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
python main.py
```

Or on Arch Linux:

```bash
sudo pacman -S tesseract tesseract-data-vie poppler
pip install -r requirements.txt
```

### Environment Variables

| Variable | Description | Default |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token | Required |
| `LLM_API_KEY` | API key for LLM (use "ollama" for local) | ollama |
| `LLM_BASE_URL` | LLM API endpoint | http://localhost:11434/v1 |
| `LLM_MODEL` | LLM model name | gemma2:9b |
| `SQLITE_PATH` | SQLite database path | data/expenses.db |
| `EXCEL_PATH` | Excel export path | data/expenses.xlsx |

## Usage

### Start the bot

```bash
python main.py
```

### Commands

- `/start` - Show welcome message
- `/help` - Show usage instructions
- `/month` - Show monthly spending summary
- `/export` - Export transactions to Excel
- `/review` - Show transactions needing review

### Text Format

Send any of these formats:

- `Ăn trưa 85k ở Phở Thìn`
- `cà phê 55k tại The Coffee House`
- `GrabBike 45k`
- `2.5tr internet VNPT`

### Image/PDF

Simply send a photo or PDF document containing receipt/invoice text.

## Project Structure

```
├── main.py          # Telegram bot handlers
├── config.py        # Configuration management
├── ocr.py           # Image/PDF OCR processing (Vietnamese + English)
├── extractor.py     # LLM-based transaction extraction
├── database.py      # SQLite database operations
├── storage.py       # Excel export functionality
├── utils.py         # Helper functions and error handling
├── requirements.txt # Python dependencies
├── Dockerfile       # Container deployment
├── flake.nix        # Nix development environment
└── README.md        # Documentation
```

## Development

### Run tests

```bash
python test_extraction.py
python test_cases.py
```

### Docker deployment

```bash
docker build -t finance-bot .
docker run -d --env-file .env -v $(pwd)/data:/app/data finance-bot
```

### Using Nix

```bash
# Enter development shell
nix develop

# Run the bot
python main.py
```

## License

MIT
