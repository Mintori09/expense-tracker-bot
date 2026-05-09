"""Multi-language support for the bot."""

# English translations
# Vietnamese first as default
MESSAGES = {
    "vi": {
        "help_text": """*Lệnh Bot Tài Chính*

/list - Xem giao dịch gần đây
/export - Xuất Excel (cách dùng: /export [today|week|month|year])
/stats - Thống kê chi tiêu hàng tháng
/review - Xem giao dịch cần kiểm tra
/language - Đổi ngôn ngữ (/language en|vi)
/getId - Lấy Chat ID và User ID

💡 Mẹo: Gửi trực tiếp nội dung chi tiêu như "30k đánh cầu" để thêm ngay!""",
        "language_set": "🌐 *Ngôn ngữ đã chuyển sang:* ",
        "language_updated": "Đã lưu tùy chọn ngôn ngữ!",
        "saved": "Đã lưu! *{amount:,.0f}* VND tại *{merchant}*",
        "duplicate": "Có thể trùng lặp. Bạn có chắc muốn thêm?",
        "export_success": "Đã xuất {count} giao dịch cho {period}",
        "no_transactions": "Không tìm thấy giao dịch nào.",
        "error_extraction": "Không thể trích xuất thông tin. Vui lòng kiểm tra định dạng.",
        "language_prompt": "Chọn ngôn ngữ / Choose language:",
    },
    "en": {
        "help_text": """*Finance Bot Commands*

/list - Show recent transactions
/export - Export to Excel (usage: /export [today|week|month|year])
/stats - Monthly spending summary
/review - Review transactions needing attention
/language - Change language (/language en|vi)
/getId - Get Chat ID and User ID

💡 Tip: Just send any expense text like "30k đánh cầu" to add directly!""",
        "language_set": "🌐 *Language set to:* ",
        "language_updated": "Language preference saved!",
        "saved": "Saved! *{amount:,.0f}* VND at *{merchant}*",
        "duplicate": "Possible duplicate found. Did you mean to add this?",
        "export_success": "Exported {count} transactions for {period}",
        "no_transactions": "No transactions found.",
        "error_extraction": "Could not extract transaction info. Please check format.",
        "language_prompt": "Choose language / Chọn ngôn ngữ:",
    },
}


def get_message(key: str, lang: str = "en", **kwargs) -> str:
    """Get translated message with optional formatting."""
    msg = MESSAGES.get(lang, MESSAGES["en"]).get(key, MESSAGES["en"].get(key, key))
    return msg.format(**kwargs) if kwargs else msg


__all__ = ["MESSAGES", "get_message"]
