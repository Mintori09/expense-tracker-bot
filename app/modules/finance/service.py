"""Finance module service layer - business logic."""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from app.modules.finance.extractor import (
    ExtractedTransaction,
    extract_multiple_fallback,
    extract_simple_fallback,
    extract_transaction,
    extract_transactions,
)
from app.modules.finance.repository import (
    Transaction,
    add_transaction,
    find_duplicates,
    init_db_schema,
)
from app.modules.finance.storage import export_to_excel
from app.shared.exceptions import ExtractionError

logger = logging.getLogger(__name__)


async def process_expense_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    source_type: str = "text",
) -> None:
    """Process and store extracted transaction."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    if not update.message:
        return

    # Get user_id for data isolation
    user_id = update.effective_user.id if update.effective_user else None

    # Get user language
    from app.core.database import get_user_language

    lang = get_user_language(user_id) if user_id else "vi"

    logger.info(
        "Processing expense text: %r from %s (user_id: %s, lang: %s)",
        text,
        source_type,
        user_id,
        lang,
    )

    try:
        # Try multi-transaction extraction first (for invoices with multiple items)
        transactions = await extract_transactions(text, source_type)

        if transactions and len(transactions) > 1:
            # Multiple transactions found - show all for confirmation
            msg = f"*Found {len(transactions)} items:*\n\n"
            total = 0
            for i, tx in enumerate(transactions, 1):
                msg += f"{i}. {tx.description or 'Item'}: {tx.amount:,.0f} VND\n"
                total += tx.amount

            msg += f"\n*Total: {total:,.0f} VND*\n\n"
            msg += "Send 'save' to save all, or send individual item text to edit."

            # Store user_id with transactions
            for tx in transactions:
                tx.user_id = user_id

            context.user_data["pending_txs"] = transactions

            keyboard = [
                [InlineKeyboardButton("Save All", callback_data="saveall")],
                [InlineKeyboardButton("Edit Items", callback_data="editmulti")],
                [InlineKeyboardButton("Cancel", callback_data="cancel")],
            ]

            await update.message.reply_text(
                msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )
            return

        extracted = await extract_transaction(text, source_type)
        extracted.user_id = user_id

        logger.info(
            "LLM extracted: amount=%s, merchant=%s, confidence=%s",
            extracted.amount,
            extracted.merchant,
            extracted.confidence,
        )

        await _confirm_and_store(update, context, extracted, user_id, lang)

    except ExtractionError as e:
        logger.warning("LLM extraction failed: %s, trying fallback", e)

        # Try to get realtime USD rate
        usd_rate = USD_TO_VND_RATE
        if "$" in text or "usd" in text.lower() or "dollar" in text.lower():
            try:
                from app.modules.finance.extractor import get_usd_to_vnd_rate
                usd_rate = await get_usd_to_vnd_rate()
                logger.info(f"Using USD rate: {usd_rate}")
            except Exception as rate_error:
                logger.warning(f"Failed to get USD rate: {rate_error}")

        # Try multiple transactions fallback first
        multiple_txs = extract_multiple_fallback(text)
        if multiple_txs and len(multiple_txs) > 1:
            # Handle multiple transactions from fallback
            msg = f"*Found {len(multiple_txs)} items:*\n\n"
            total = 0
            for i, tx in enumerate(multiple_txs, 1):
                msg += f"{i}. {tx.description}: {tx.amount:,.0f} VND\n"
                total += tx.amount

            msg += f"\n*Total: {total:,.0f} VND*\n\n"
            msg += "Send 'save' to save all, or send individual item text to edit."

            # Store user_id with transactions
            for tx in multiple_txs:
                tx.user_id = user_id

            context.user_data["pending_txs"] = multiple_txs

            keyboard = [
                [InlineKeyboardButton("Save All", callback_data="saveall")],
                [InlineKeyboardButton("Edit Items", callback_data="editmulti")],
                [InlineKeyboardButton("Cancel", callback_data="cancel")],
            ]

            await update.message.reply_text(
                msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )
            return

        fallback = extract_simple_fallback(text, usd_rate)

        if fallback:
            fallback.user_id = user_id
            await _confirm_and_store(update, context, fallback, user_id, lang)
        else:
            from app.i18n import get_message

            await update.message.reply_text(get_message("error_extraction", lang))

    except Exception:
        logger.exception("Unexpected error processing text")
        from app.i18n import get_message

        await update.message.reply_text(get_message("error_extraction", lang))


async def _confirm_and_store(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    tx: ExtractedTransaction,
    user_id: int = None,
    lang: str = "vi",
) -> None:
    """Confirm transaction with user and store if approved."""
    import uuid

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    if not update.message:
        return

    duplicates = find_duplicates(tx.merchant or "", tx.amount, tx.date)

    msg = "*Xác nhận chi tiêu:*\n\n" if lang == "vi" else "*Confirm expense:*\n\n"
    msg += f"Ngày: {tx.date}\n" if lang == "vi" else f"Date: {tx.date}\n"
    msg += f"Mô tả: {tx.description}\n" if lang == "vi" else f"Description: {tx.description}\n"
    msg += f"Cửa hàng: {tx.merchant or 'Không rõ'}\n" if lang == "vi" else f"Merchant: {tx.merchant or 'Unknown'}\n"
    msg += f"Số tiền: {tx.amount:,.0f} {tx.currency}\n" if lang == "vi" else f"Amount: {tx.amount:,.0f} {tx.currency}\n"
    msg += f"Danh mục: {tx.category}\n" if lang == "vi" else f"Category: {tx.category}\n"
    msg += f"Độ tin cậy: {tx.confidence * 100:.0f}%\n" if lang == "vi" else f"Confidence: {tx.confidence * 100:.0f}%\n"

    if duplicates:
        msg += "\n*Có thể trùng lặp!*" if lang == "vi" else "\n*Possible duplicate detected!*"

    if tx.needs_review or tx.confidence < 0.8:
        msg += "\n\n*Cần xác nhận của bạn*" if lang == "vi" else "\n\n*Needs your confirmation*"

        # Generate unique pending ID
        pending_id = str(uuid.uuid4())[:8]
        context.user_data["pending_tx"] = tx
        context.user_data[f"pending_tx_{pending_id}"] = tx

        keyboard = [
            [
                InlineKeyboardButton("Confirm", callback_data=f"confirm:{pending_id}"),
                InlineKeyboardButton("Edit", callback_data=f"edit:{pending_id}"),
                InlineKeyboardButton("Cancel", callback_data=f"cancel:{pending_id}"),
            ],
        ]

        await update.message.reply_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    else:
        transaction = Transaction(
            date=tx.date,
            merchant=tx.merchant,
            amount=tx.amount,
            currency=tx.currency,
            category=tx.category,
            payment_method=tx.payment_method,
            description=tx.description,
            source_type=tx.source_type,
            confidence=tx.confidence,
            needs_review=tx.needs_review,
            user_id=user_id,
        )

        add_transaction(transaction, tx.description or "")
        export_to_excel()

        msg += "\n\n*Đã thêm vào cơ sở dữ liệu!*" if lang == "vi" else "\n\n*Added to database!*"

        await update.message.reply_text(msg, parse_mode="Markdown")


def _handle_error(error: Exception, context: Optional[str] = None) -> str:
    """Generate user-friendly error message."""
    from app.shared.exceptions import handle_error as shared_handle_error

    return shared_handle_error(error, context)


__all__ = ["process_expense_text", "init_db_schema"]

