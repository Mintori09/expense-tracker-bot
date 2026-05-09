"""
Main Telegram bot module.
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path

from telegram import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import ensure_data_dir, settings
from database import (
    Transaction,
    add_transaction,
    find_duplicates,
    get_monthly_summary,
    init_schema,
)
from extractor import ExtractedTransaction, extract_simple_fallback, extract_transaction
from ocr import image_to_text_async, pdf_to_text_async, preprocess_ocr_text
from storage import export_to_excel
from utils import ExtractionError, handle_error

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message."""
    if not update.message:
        return

    user = update.effective_user

    await update.message.reply_html(
        rf"Hi {user.first_name if user else 'there'}! I'm your finance automation bot.\n\n"
        "Send me:\n"
        '• Text: "Ăn trưa 85k ở Phở Thìn"\n'
        "• Images: Receipt photos\n"
        "• PDFs: Invoice documents\n\n"
        "Commands:\n"
        "/month - Monthly summary\n"
        "/help - Show help",
        reply_markup=ForceReply(selective=True),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help message."""
    if not update.message:
        return

    await update.message.reply_text(
        "*How to use:*\n\n"
        "*Text:* Send expense text like:\n"
        '• "Ăn trưa 85k ở Phở Thìn"\n'
        '• "cà phê 55k tại The Coffee House"\n\n'
        "*Image:* Send receipt photo\n"
        "*PDF:* Send invoice document\n\n"
        "*Commands:*\n"
        "/month - Show monthly spending\n"
        "/export - Export to Excel\n"
        "/review - Show transactions needing review\n\n"
        "*Edit format:* /edit amount=90000 category=Food merchant=Phở Thìn",
        parse_mode="Markdown",
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages containing expenses."""
    logger.info("handle_text CALLED")

    if not update.message:
        logger.warning("No update.message")
        return

    logger.info("Received text: %r", update.message.text)

    if not update.message.text:
        logger.warning("Message has no text")
        return

    text = update.message.text.strip()

    if not text:
        await update.message.reply_text("Please send some expense text.")
        return

    # Check if we're in edit mode (waiting for field value)
    editing_field = context.user_data.pop("editing_field", None)
    if editing_field:
        tx_data = context.user_data.get("pending_tx")
        if not tx_data:
            await update.message.reply_text("*No pending transaction found.*")
            return

        try:
            # Update the field
            if editing_field == "amount":
                tx_data.amount = float(text.replace(",", "."))
            elif editing_field == "merchant":
                tx_data.merchant = text
            elif editing_field == "category":
                tx_data.category = text
            elif editing_field == "date":
                tx_data.date = text
            elif editing_field == "payment_method":
                tx_data.payment_method = text

            context.user_data["pending_tx"] = tx_data

            # Show updated menu
            await show_edit_menu(update, context, tx_data)
            return

        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
            return

    await process_expense_text(update, context, text, source_type="text")


async def process_expense_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    source_type: str = "text",
) -> None:
    """Process and store extracted transaction."""
    if not update.message:
        return

    logger.info("Processing expense text: %r from %s", text, source_type)

    try:
        extracted = await extract_transaction(text, source_type)

        logger.info(
            "LLM extracted: amount=%s, merchant=%s, confidence=%s",
            extracted.amount,
            extracted.merchant,
            extracted.confidence,
        )

        await confirm_and_store(update, context, extracted)

    except ExtractionError as e:
        logger.warning("LLM extraction failed: %s, trying fallback", e)

        fallback = extract_simple_fallback(text)

        if fallback:
            await confirm_and_store(update, context, fallback)
        else:
            await update.message.reply_text(
                handle_error(ExtractionError("Could not extract"))
            )

    except Exception as e:
        logger.exception("Unexpected error processing text")
        await update.message.reply_text(handle_error(e, "Processing error"))


async def confirm_and_store(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    tx: ExtractedTransaction,
) -> None:
    """Confirm transaction with user and store if approved."""
    if not update.message:
        return

    duplicates = find_duplicates(tx.merchant or "", tx.amount, tx.date)

    msg = "*Confirm expense:*\n\n"
    msg += f"Date: {tx.date}\n"
    msg += f"Merchant: {tx.merchant or 'Unknown'}\n"
    msg += f"Amount: {tx.amount:,.0f} {tx.currency}\n"
    msg += f"Category: {tx.category}\n"
    msg += f"Confidence: {tx.confidence * 100:.0f}%\n"

    if duplicates:
        msg += "\n*Possible duplicate detected!*"

    if tx.needs_review or tx.confidence < 0.8:
        msg += "\n\n*Needs your confirmation*"

        # Generate unique pending ID
        pending_id = str(uuid.uuid4())[:8]
        context.user_data["pending_tx"] = tx
        context.user_data[f"pending_tx_{pending_id}"] = tx

        keyboard = [
            [
                InlineKeyboardButton(
                    "Confirm", callback_data=f"confirm:{pending_id}"
                ),
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
        )

        add_transaction(transaction, tx.description or "")
        export_to_excel()

        msg += "\n\n*Added to database!*"

        await update.message.reply_text(msg, parse_mode="Markdown")


async def handle_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /edit command - starts interactive edit flow."""
    if not update.message:
        return

    # Check if there's a pending transaction
    tx_data = context.user_data.get("pending_tx")

    if not tx_data:
        await update.message.reply_text(
            "*No pending transaction to edit.*\n\n"
            "Send an expense first, then use Edit button to modify.",
            parse_mode="Markdown",
        )
        return

    # Show field selection keyboard (interactive edit mode)
    await show_edit_menu(update, context, tx_data)


async def show_edit_menu(update_or_query, context: ContextTypes.DEFAULT_TYPE, tx_data):
    """Show interactive edit menu."""
    keyboard = [
        [
            InlineKeyboardButton("Amount", callback_data="editfield:amount"),
            InlineKeyboardButton("Merchant", callback_data="editfield:merchant"),
            InlineKeyboardButton("Category", callback_data="editfield:category"),
        ],
        [
            InlineKeyboardButton("Date", callback_data="editfield:date"),
            InlineKeyboardButton("Payment", callback_data="editfield:payment_method"),
        ],
        [
            InlineKeyboardButton("Save", callback_data="editsave"),
            InlineKeyboardButton("Cancel", callback_data="cancel"),
        ],
    ]

    msg = "*Edit Transaction*\n\n"
    msg += f"Current values:\n"
    msg += f"  *Amount:* {tx_data.amount:,.0f}\n"
    msg += f"  *Merchant:* {tx_data.merchant or 'Unknown'}\n"
    msg += f"  *Category:* {tx_data.category}\n"
    msg += f"  *Date:* {tx_data.date}\n"
    msg += f"  *Payment:* {tx_data.payment_method}\n\n"
    msg += "Select a field to edit:"

    if hasattr(update_or_query, 'message'):
        await update_or_query.message.reply_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    else:
        await update_or_query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle receipt photos."""
    if not update.message or not update.message.photo:
        return

    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)

        ensure_data_dir()

        sanitized_id = "".join(c for c in photo.file_id if c.isalnum() or c in "-_")
        image_path = f"data/temp_{sanitized_id}.jpg"
        await file.download_to_drive(image_path)

        await update.message.reply_text("Processing image...", parse_mode="Markdown")

        try:
            text = await image_to_text_async(image_path)
            text = preprocess_ocr_text(text)

            await update.message.reply_text(
                f"*OCR extracted:*\n```\n{text[:200]}...\n```",
                parse_mode="Markdown",
            )

            await process_expense_text(update, context, text, source_type="image")
        finally:
            Path(image_path).unlink(missing_ok=True)

    except Exception as e:
        logger.exception("Image processing error")
        await update.message.reply_text(handle_error(e, "Image processing"))


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle PDF documents."""
    if not update.message or not update.message.document:
        return

    try:
        doc = update.message.document

        if not doc.file_name or not doc.file_name.lower().endswith(".pdf"):
            await update.message.reply_text("Please send a PDF file.")
            return

        file = await context.bot.get_file(doc.file_id)

        ensure_data_dir()

        sanitized_id = "".join(c for c in doc.file_id if c.isalnum() or c in "-_")
        pdf_path = f"data/temp_{sanitized_id}.pdf"
        await file.download_to_drive(pdf_path)

        await update.message.reply_text("Processing PDF...", parse_mode="Markdown")

        try:
            text = await pdf_to_text_async(pdf_path)
            text = preprocess_ocr_text(text)

            await update.message.reply_text(
                f"*PDF extracted:*\n```\n{text[:200]}...\n```",
                parse_mode="Markdown",
            )

            await process_expense_text(update, context, text, source_type="pdf")
        finally:
            Path(pdf_path).unlink(missing_ok=True)

    except Exception as e:
        logger.exception("PDF processing error")
        await update.message.reply_text(handle_error(e, "PDF processing"))


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button callbacks."""
    query = update.callback_query

    if not query:
        return

    await query.answer()

    data = query.data or ""
    parts = data.split(":")
    action = parts[0]
    param = parts[1] if len(parts) > 1 else None

    # Helper to get transaction by pending_id
    def get_tx_by_id(pid):
        if not pid:
            return context.user_data.get("pending_tx")
        return context.user_data.get(f"pending_tx_{pid}")

    # Handle edit menu - show field selection
    if action == "edit" and param:
        tx_data = get_tx_by_id(param)
        if not tx_data:
            await query.edit_message_text("*Transaction not found.*")
            return
        await show_edit_menu(query, context, tx_data)
        return

    # Handle edit field selection - prompt for new value
    if action == "editfield" and param:
        tx_data = context.user_data.get("pending_tx")
        if not tx_data:
            await query.edit_message_text("*No transaction found.*")
            return

        # Store which field we're editing
        context.user_data["editing_field"] = param

        field_name = param.replace("_", " ").title()
        await query.edit_message_text(
            f"*Enter new {field_name}:*",
            parse_mode="Markdown",
        )
        return

    # Handle save after edit
    if action == "editsave":
        tx_data = context.user_data.get("pending_tx")
        if not tx_data:
            await query.edit_message_text("*No transaction found.*")
            return

        transaction = Transaction(
            date=tx_data.date,
            merchant=tx_data.merchant,
            amount=tx_data.amount,
            currency=tx_data.currency,
            category=tx_data.category,
            payment_method=tx_data.payment_method,
            description=tx_data.description,
            source_type=tx_data.source_type,
            confidence=tx_data.confidence,
            needs_review=tx_data.needs_review,
        )

        add_transaction(transaction, tx_data.description or "")
        export_to_excel()

        # Clean up
        context.user_data.pop("pending_tx", None)
        context.user_data.pop("editing_field", None)

        await query.edit_message_text(
            "*Transaction saved!*",
            parse_mode="Markdown",
        )
        return

    if action == "confirm":
        tx_data = get_tx_by_id(param)
        if not tx_data:
            await query.edit_message_text("*No pending transaction found.*")
            return

        transaction = Transaction(
            date=tx_data.date,
            merchant=tx_data.merchant,
            amount=tx_data.amount,
            currency=tx_data.currency,
            category=tx_data.category,
            payment_method=tx_data.payment_method,
            description=tx_data.description,
            source_type=tx_data.source_type,
            confidence=tx_data.confidence,
            needs_review=tx_data.needs_review,
        )

        add_transaction(transaction, tx_data.description or "")
        export_to_excel()

        # Clean up
        if param:
            context.user_data.pop(f"pending_tx_{param}", None)
        context.user_data.pop("pending_tx", None)

        await query.edit_message_text(
            "*Transaction confirmed and saved!*",
            parse_mode="Markdown",
        )
        return

    elif action == "cancel":
        if param:
            context.user_data.pop(f"pending_tx_{param}", None)
        context.user_data.pop("pending_tx", None)
        context.user_data.pop("editing_field", None)
        await query.edit_message_text("*Transaction cancelled.*")
        return

    elif action == "edit":
        tx_data = get_tx_by_id(param)
        if not tx_data:
            await query.edit_message_text("*No pending transaction found.*")
            return
        await show_edit_menu(query, context, tx_data)
        return


async def month_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show monthly spending summary."""
    if not update.message:
        return

    now = datetime.now()
    summary = get_monthly_summary(now.year, now.month)

    msg = f"*Monthly Summary - {now.strftime('%B %Y')}*\n\n"
    msg += f"Total spent: {summary['total_spent']:,.0f} VND\n\n"

    if summary["categories"]:
        msg += "*By category:*\n"

        for cat, amount in sorted(
            summary["categories"].items(),
            key=lambda item: -item[1],
        ):
            msg += f"  * {cat}: {amount:,.0f} VND\n"
    else:
        msg += "No expenses this month yet."

    await update.message.reply_text(msg, parse_mode="Markdown")


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export transactions to Excel."""
    if not update.message:
        return

    try:
        path = export_to_excel()

        await update.message.reply_text(
            f"*Exported to* `{path}`",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.exception("Export error")
        await update.message.reply_text(handle_error(e))


async def review_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show transactions needing review."""
    if not update.message:
        return

    from database import get_needs_review_transactions

    txs = get_needs_review_transactions()

    if not txs:
        await update.message.reply_text("*No transactions need review.*")
        return

    msg = f"*Transactions needing review: {len(txs)}*\n\n"

    for tx in txs[:10]:
        msg += (
            f"  * {tx.date} - "
            f"{tx.amount:,.0f} VND - "
            f"{tx.merchant or 'Unknown'} "
            f"({tx.confidence * 100:.0f}%)\n"
        )

    await update.message.reply_text(msg, parse_mode="Markdown")


def main() -> None:
    """Start the bot."""
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    init_schema()

    application = Application.builder().token(settings.telegram_bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("month", month_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("review", review_command))
    application.add_handler(CommandHandler("edit", handle_edit))

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.PDF, handle_document))

    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()