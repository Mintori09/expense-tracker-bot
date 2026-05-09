# Telegram Finance Bot - Tài liệu Cấu trúc & Chức năng

Tài liệu ghi lại cấu trúc thư mục, các module và hàm quan trọng của dự án.

---

## Cấu trúc Thư mục

```
telegram-bot/
├── main.py              # Module chính, xử lý Telegram bot handlers
├── config.py            # Cấu hình ứng dụng, biến môi trường
├── database.py          # Module quản lý SQLite database
├── extractor.py         # Trích xuất giao dịch bằng LLM
├── ocr.py               # Xử lý OCR cho ảnh và PDF
├── storage.py           # Xuất dữ liệu sang Excel
├── utils.py             # Hàm tiện ích, xử lý lỗi
├── test_cases.py        # Test cases cho bot
├── test_extraction.py # Test trích xuất
├── test_fixes.py        # Test sửa lỗi
├── requirements.txt     # Dependencies
├── Dockerfile           # Docker configuration
└── data/                # Thư mục chứa database và file xuất
```

---

## Module Chi tiết

### 1. main.py - Telegram Bot Handlers

**Mô tả:** Module chính điều khiển các handler Telegram bot.

| Hàm                      | Loại  | Tác dụng                                           |
| ------------------------ | ----- | -------------------------------------------------- |
| `start()`                | async | Gửi tin nhắn chào mừng khi người dùng bắt đầu      |
| `help_command()`         | async | Hiển thị hướng dẫn sử dụng bot                     |
| `handle_text()`          | async | Xử lý tin nhắn text chứa chi tiết chi tiêu         |
| `process_expense_text()` | async | Trích xuất và lưu giao dịch từ text                |
| `confirm_and_store()`    | async | Xác nhận giao dịch với người dùng và lưu DB        |
| `handle_photo()`         | async | Xử lý ảnh biên lai, OCR rồi trích xuất             |
| `handle_document()`      | async | Xử lý file PDF biên lai                            |
| `button_callback()`      | async | Xử lý callback từ nút inline (confirm/edit/cancel) |
| `month_command()`        | async | Hiển thị tổng chi tiêu theo tháng                  |
| `export_command()`       | async | Xuất giao dịch ra file Excel                       |
| `review_command()`       | async | Hiển thị các giao dịch cần xem xét                 |
| `main()`                 | sync  | Khởi động bot                                      |

---

### 2. config.py - Cấu hình

**Mô tả:** Quản lý cấu hình ứng dụng từ biến môi trường.

```python
class Settings(BaseSettings):
    telegram_bot_token: str              # Token bot Telegram
    llm_api_key: str                     # API key cho LLM (mặc định: ollama)
    llm_base_url: str                    # URL API LLM
    llm_model: str                       # Model LLM (gemma3:4b-it-qat)
    ollama_host: str                     # Host Ollama
    ollama_model: str                    # Model Ollama
    sqlite_path: str                     # Đường dẫn database SQLite
    excel_path: str                      # Đường dẫn file Excel xuất
    log_level: str                       # Mức độ log
    default_categories: list[str]        # Danh sách category mặc định
    merchant_category_map: dict[str, str] # Map merchant -> category đã học
```

| Hàm                 | Tác dụng                          |
| ------------------- | --------------------------------- |
| `ensure_data_dir()` | Tạo thư mục data nếu chưa tồn tại |

---

### 3. database.py - Quản lý Database

**Mô tả:** Module thao tác SQLite để lưu trữ giao dịch.

```python
@dataclass
class Transaction:
    date: str              # Ngày giao dịch (YYYY-MM-DD)
    merchant: str            # Tên merchant
    amount: float            # Số tiền
    currency: str            # Loại tiền (VND)
    category: str            # Danh mục chi tiêu
    payment_method: str      # Phương thức thanh toán
    description: str         # Mô tả
    source_type: str         # Loại nguồn (text/image/pdf)
    confidence: float        # Độ tin cậy (0-1)
    needs_review: bool       # Cần xem xét
    id: Optional[int]      # ID database
```

| Hàm                                       | Tác dụng                               |
| ----------------------------------------- | -------------------------------------- |
| `init_db()`                               | Khởi tạo database và bảng transactions |
| `add_transaction(tx)`                     | Thêm giao dịch mới vào database        |
| `get_monthly_summary(year, month)`        | Lấy tổng chi tiêu theo tháng           |
| `find_duplicates(merchant, amount, date)` | Tìm giao dịch trùng lặp                |
| `get_transactions(limit)`                 | Lấy danh sách giao dịch gần đây        |
| `get_needs_review_transactions()`         | Lấy giao dịch cần xem xét              |
| `learn_category(merchant, category)`      | Ghi nhớ mapping merchant-category      |

---

### 4. extractor.py - Trích xuất Giao dịch

**Mô tả:** Module sử dụng LLM và fallback để trích xuất dữ liệu giao dịch.

```python
@dataclass
class ExtractedTransaction:
    date: str                # Ngày
    merchant: Optional[str]   # Tên merchant
    amount: float              # Số tiền
    currency: str              # Loại tiền
    category: str              # Danh mục
    payment_method: str        # Phương thức thanh toán
    description: str           # Mô tả
    source_type: str           # Loại nguồn
    confidence: float          # Độ tin cậy
    needs_review: bool         # Cần xem xét
```

| Hàm                                           | Loại  | Tác dụng                                     |
| --------------------------------------------- | ----- | -------------------------------------------- |
| `get_category_for_merchant(merchant)`         | sync  | Lấy category đã học cho merchant             |
| `learn_merchant_category(merchant, category)` | sync  | Học mapping mới merchant-category            |
| `parse_vietnamese_amount(text)`               | sync  | Parse số tiền định dạng Việt (85k, 2.5tr...) |
| `call_llm(prompt)`                            | async | Gọi API LLM để trích xuất                    |
| `get_system_prompt()`                         | sync  | Tạo system prompt cho LLM                    |
| `extract_transaction(text, source_type)`      | async | Trích xuất giao dịch bằng LLM                |
| `extract_simple_fallback(text)`               | sync  | Trích xuất dự phòng không cần LLM            |

---

### 5. ocr.py - OCR Processing

**Mô tả:** Xử lý OCR cho ảnh và PDF tiếng Việt + Anh.

| Hàm                         | Loại | Tác dụng                               |
| --------------------------- | ---- | -------------------------------------- |
| `setup_tesseract()`         | sync | Cấu hình Tesseract cho tiếng Việt/Anh  |
| `image_to_text(image_path)` | sync | Trích xuất text từ ảnh                 |
| `pdf_to_text(pdf_path)`     | sync | Trích xuất text từ PDF                 |
| `preprocess_ocr_text(text)` | sync | Làm sạch text OCR (sửa lỗi O->0, l->1) |

---

### 6. storage.py - Excel Export

**Mô tả:** Module xuất dữ liệu giao dịch sang file Excel.

| Hàm                                   | Loại | Tác dụng                           |
| ------------------------------------- | ---- | ---------------------------------- |
| `export_to_excel(transactions)`       | sync | Xuất giao dịch ra file Excel       |
| `export_monthly_summary(year, month)` | sync | Xuất tổng hợp tháng ra sheet riêng |

---

### 7. utils.py - Utilities

**Mô tả:** Module hàm tiện ích và xử lý lỗi.

```python
class ExtractionError(Exception):    # Lỗi khi trích xuất LLM thất bại
class OCRFailedError(Exception):     # Lỗi khi OCR thất bại
class InvalidTransactionError(Exception):  # Lỗi dữ liệu giao dịch không hợp lệ
```

| Hàm                            | Loại | Tác dụng                     |
| ------------------------------ | ---- | ---------------------------- |
| `setup_logging()`              | sync | Cấu hình logging             |
| `handle_error(error, context)` | sync | Tạo thông báo lỗi thân thiện |

---

## Luồng Xử lý Chính

```
1. Người dùng gửi tin nhắn (text/ảnh/PDF)
   ↓
2. main.py handler nhận tin nhắn
   ↓
3. Nếu ảnh/PDF → ocr.py xử lý → text
   ↓
4. extractor.py:
   - Thử LLM extract_transaction()
   - Nếu lỗi → dùng extract_simple_fallback()
   ↓
5. confirm_and_store():
   - Kiểm tra trùng lặp
   - Hiển thị xác nhận hoặc tự động lưu
   ↓
6. database.py lưu vào SQLite
   ↓
7. storage.py export sang Excel
```

---

## Định dạng Dữ liệu Đầu vào

### Text

- `"Ăn trưa 85k ở Phở Thìn"` → 85,000 VND, category Food
- `"cà phê 55k tại The Coffee House"` → 55,000 VND, category Coffee
- `"2.5tr internet VNPT"` → 2,500,000 VND, category Other
- `"Netflix 260k/tháng"` → 260,000 VND, category Subscription

### Ảnh/PDF

- Biên lai, hoá đơn cần OCR
- Hỗ trợ tiếng Việt + Anh

---

## Categories Hỗ trợ

- Food, Coffee, Groceries, Transport
- Rent, Utilities, Shopping, Health
- Education, Entertainment, Travel
- Subscription, Income, Other

---

## Commands Telegram

| Command   | Mô tả                     |
| --------- | ------------------------- |
| `/start`  | Bắt đầu bot               |
| `/help`   | Xem hướng dẫn             |
| `/month`  | Xem tổng chi tháng        |
| `/export` | Xuất Excel                |
| `/review` | Xem giao dịch cần xem xét |

