# PLAN - Cải tiến Bot Telegram

## Context
Cần cải tiến UX người dùng:
1. Auto-suggest lệnh khi gõ "/"
2. Giao diện edit thân thiện hơn bằng inline buttons

## Changes Made

### 1. Fix syntax `__name__` lỗi
- ✅ Kiểm tra: Không tìm thấy `**name**` nào trong codebase

### 2. Database refactoring
- ✅ Tách `get_connection()` và `init_schema()` riêng biệt
- ✅ Dùng context manager `get_db_cursor()` để tránh leak/lock
- ✅ Thêm bảng `merchant_categories` để lưu category đã học
- ✅ Thêm `source_hash` UNIQUE để tránh ghi trùng khi retry
- ✅ Cải thiện `find_duplicates` với tolerance theo % và normalize merchant

### 3. OCR improvement
- ✅ Thử `pdfplumber` đọc text PDF trước, fallback OCR nếu cần
- ✅ Cleanup temp files sau khi xử lý

### 4. ExtractedTransaction Pydantic
- ✅ Convert thành `BaseModel` với validation cho amount, date, category

### 5. User feedback
- ✅ Thông báo "Processing image/PDF..." khi đang xử lý
- ✅ Bỏ emoji, dùng Markdown **bold** để highlight

## Pending Changes (cần implement)

### 6. Auto-suggest commands
Khi người dùng gõ "/", hiển thị gợi ý lệnh:
- /start - Bắt đầu bot
- /month - Xem chi tiêu tháng
- /export - Xuất Excel
- /review - Duyệt giao dịch
- /edit - Sửa giao dịch

### 7. Interactive Edit Flow
Thay vì `/edit amount=90000 category=Food`, dùng flow:
1. User nhấn nút "Edit" trên pending transaction
2. Bot hiển thị menu chọn field: Amount, Merchant, Category, Date, Payment
3. User chọn field, bot yêu cầu nhập giá trị mới
4. User nhập giá trị, bot cập nhật và hỏi Confirm/Save

**Files to modify:**
- `main.py` - Thêm handlers cho edit flow

**Reuse:**
- `context.user_data["pending_tx"]` - lưu transaction tạm
- `context.user_data["edit_state"]` - lưu field đang edit

**Verification:**
- Chạy bot, test flow: gửi expense → nhấn Edit → chọn field → nhập giá trị → save