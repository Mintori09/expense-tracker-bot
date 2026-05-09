"""Finance module handlers - Telegram message handlers."""

import logging
from datetime import datetime
from pathlib import Path

from telegram import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.config import settings
from app.modules.finance.ocr import (
    image_to_text_async,
    pdf_to_text_async,
    preprocess_ocr_text,
)
from app.modules.finance.repository import (
    Transaction,
    add_transaction,
    delete_transaction,
    get_monthly_summary,
    get_needs_review_transactions,
    get_today_transactions,
    get_transaction,
    get_transactions,
    update_transaction,
    get_current_balance,
    get_initial_balance,
    set_initial_balance,
)
from app.modules.finance.service import process_expense_text
from app.modules.finance.storage import export_to_excel, export_period_to_excel
from app.shared.exceptions import handle_error

logger = logging.getLogger(__name__)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        "/today - Show today's expenses\n"
        "/current - Show current balance\n"
        "/setbalance - Set initial balance\n"
        "/export - Export all to Excel\n"
        "/export today|week|month|year - Export by period\n"
        "/review - Show transactions needing review\n"
        "/edit - Edit pending transaction\n"
        "/remove <id> - Remove a transaction\n"
        "/getId - Get current chat ID\n\n"
        "*Edit:* After confirming, use inline buttons to edit fields.",
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


async def handle_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /edit command - starts interactive edit flow."""
    if not update.message:
        return

    text = update.message.text.strip()

    # Check if user wants to edit a specific transaction by ID
    parts = text.split()
    if len(parts) > 1:
        try:
            tx_id = int(parts[1])

            tx_to_edit = get_transaction(tx_id)
            if tx_to_edit:
                context.user_data["pending_tx"] = tx_to_edit
                await show_edit_menu(update, context, tx_to_edit)
                return
            else:
                await update.message.reply_text("*Transaction not found.*")
                return
        except ValueError:
            pass

    # Check if there's a pending transaction
    tx_data = context.user_data.get("pending_tx")

    if tx_data:
        # Show field selection keyboard (interactive edit mode)
        await show_edit_menu(update, context, tx_data)
        return

    # No pending transaction - show recent transactions to edit
    recent_txs = get_transactions(10)
    if not recent_txs:
        await update.message.reply_text(
            "*No transactions found to edit.*\n\n"
            "Send an expense first, then use Edit button to modify.",
            parse_mode="Markdown",
        )
        return

    # Show recent transactions with edit option
    msg = "*Recent transactions (reply /edit <id> to modify):*\n\n"
    for tx in recent_txs[:5]:
        msg += f"• `{tx.id}` {tx.date} - {tx.amount:,.0f} VND - {tx.merchant or 'Unknown'}\n"

    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
    )


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
    msg += "Current values:\n"
    msg += f"  *Amount:* {tx_data.amount:,.0f}\n"
    msg += f"  *Merchant:* {tx_data.merchant or 'Unknown'}\n"
    msg += f"  *Category:* {tx_data.category}\n"
    msg += f"  *Date:* {tx_data.date}\n"
    msg += f"  *Payment:* {tx_data.payment_method}\n\n"
    msg += "Select a field to edit:"

    if hasattr(update_or_query, "message"):
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

    logger.info("=== Photo handling started ===")

    try:
        from app.config import ensure_data_dir

        photo = update.message.photo[-1]
        logger.info(f"Photo file_id: {photo.file_id}, size: {photo.file_size}")

        file = await context.bot.get_file(photo.file_id)

        ensure_data_dir()

        sanitized_id = "".join(c for c in photo.file_id if c.isalnum() or c in "-_")
        image_path = f"data/finance/temp_{sanitized_id}.jpg"
        await file.download_to_drive(image_path)
        logger.info(f"Image downloaded to: {image_path}")

        await update.message.reply_text("Processing image...", parse_mode="Markdown")

        try:
            logger.info("Calling AI vision for OCR...")
            text = await image_to_text_async(image_path)
            logger.info(f"OCR raw output ({len(text)} chars): {text[:100]}...")

            text = preprocess_ocr_text(text)
            logger.info(f"OCR preprocessed: {text[:100]}...")

            await process_expense_text(update, context, text, source_type="image")
        finally:
            Path(image_path).unlink(missing_ok=True)
            logger.info(f"Temp file deleted: {image_path}")

    except Exception as e:
        logger.exception("Image processing error")
        await update.message.reply_text(handle_error(e, "Image processing"))


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle PDF documents."""
    if not update.message or not update.message.document:
        return

    logger.info("=== PDF handling started ===")

    try:
        from app.config import ensure_data_dir

        doc = update.message.document

        if not doc.file_name or not doc.file_name.lower().endswith(".pdf"):
            await update.message.reply_text("Please send a PDF file.")
            return

        logger.info(f"PDF file: {doc.file_name}, size: {doc.file_size}")

        file = await context.bot.get_file(doc.file_id)

        ensure_data_dir()

        sanitized_id = "".join(c for c in doc.file_id if c.isalnum() or c in "-_")
        pdf_path = f"data/finance/temp_{sanitized_id}.pdf"
        await file.download_to_drive(pdf_path)
        logger.info(f"PDF downloaded to: {pdf_path}")

        await update.message.reply_text("Processing PDF...", parse_mode="Markdown")

        try:
            logger.info("Calling PDF text extraction...")
            text = await pdf_to_text_async(pdf_path)
            logger.info(f"PDF extracted text ({len(text)} chars): {text[:100]}...")

            text = preprocess_ocr_text(text)
            logger.info(f"Preprocessed: {text[:100]}...")

            await update.message.reply_text(
                f"*PDF extracted:*\n```\n{text[:200]}...\n```",
                parse_mode="Markdown",
            )

            await process_expense_text(update, context, text, source_type="pdf")
        finally:
            Path(pdf_path).unlink(missing_ok=True)
            logger.info(f"Temp file deleted: {pdf_path}")

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

    # Handle save all transactions (multi-item invoice)
    if action == "saveall":
        transactions = context.user_data.get("pending_txs", [])
        if not transactions:
            await query.edit_message_text("*No transactions found.*")
            return

        for tx_data in transactions:
            user_id = tx_data.user_id
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
                user_id=user_id,
            )
            add_transaction(transaction, tx_data.description or "")

        export_to_excel()
        context.user_data.pop("pending_txs", None)

        await query.edit_message_text(
            f"*Saved {len(transactions)} transactions!*",
            parse_mode="Markdown",
        )
        return

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

    if action == "editsave":
        tx_data = context.user_data.get("pending_tx")
        if not tx_data:
            await query.edit_message_text("*No transaction found.*")
            return

        # Check if this is an existing transaction (has ID) or new
        tx_id = getattr(tx_data, "id", None)

        if tx_id:
            # Update existing transaction
            updated = update_transaction(tx_id, tx_data)
            context.user_data.pop("pending_tx", None)
            context.user_data.pop("editing_field", None)

            if updated:
                await query.edit_message_text(
                    "*Transaction updated!*",
                    parse_mode="Markdown",
                )
            else:
                await query.edit_message_text(
                    "*Failed to update.*",
                    parse_mode="Markdown",
                )
        else:
            # New transaction - add to database
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
                user_id=tx_data.user_id,
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
            user_id=tx_data.user_id,
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
    """Export transactions to Excel with period options."""
    if not update.message:
        return

    text = update.message.text.strip()
    parts = text.split()

    # Get user_id for isolation
    user_id = update.effective_user.id if update.effective_user else None

    # Default to all transactions
    period = "all"
    year = datetime.now().year
    month = datetime.now().month

    # Parse period argument: /export today|week|month|year [year] [month]
    if len(parts) > 1:
        arg = parts[1].lower()
        if arg in ("today", "week", "month", "year"):
            period = arg
            if arg == "month" and len(parts) > 2:
                try:
                    month = int(parts[2])
                except ValueError:
                    pass
            elif arg == "year" and len(parts) > 2:
                try:
                    year = int(parts[2])
                except ValueError:
                    pass

    try:
        if period == "all":
            path = settings.excel_path
            export_to_excel()
            count = len(get_transactions())
        else:
            path, count = export_period_to_excel(period, year, month, user_id)

        # Send file via Telegram
        from pathlib import Path
        if Path(path).exists():
            with open(path, "rb") as f:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=f,
                    filename=Path(path).name,
                    caption=f"*Exported {count} transaction(s) for {period}*" + 
                            (f" {year}" if period == "year" else 
                             f" {year}-{month:02d}" if period == "month" else ""),
                    parse_mode="Markdown",
                )
        else:
            await update.message.reply_text(
                f"No transactions found for {period}."
            )

    except Exception as e:
        logger.exception("Export error")
        await update.message.reply_text(handle_error(e))


async def review_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show transactions needing review."""
    if not update.message:
        return

    txs = get_needs_review_transactions()

    if not txs:
        await update.message.reply_text("*No transactions need review.*")
        return

    msg = f"*Transactions needing review: {len(txs)}*\n\n"

    for tx in txs[:10]:
        msg += (
            f"  * `{tx.id}` {tx.date} - "
            f"{tx.amount:,.0f} VND - "
            f"{tx.merchant or 'Unknown'} "
            f"({tx.confidence * 100:.0f}%)\n"
        )

    await update.message.reply_text(msg, parse_mode="Markdown")


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show today's transactions."""
    if not update.message:
        return

    txs = get_today_transactions()

    if not txs:
        await update.message.reply_text("*No expenses today.*")
        return

    total = sum(tx.amount for tx in txs)
    msg = f"*Today's expenses:* {total:,.0f} VND\n\n"

    for tx in txs:
        msg += f"• {tx.date} - {tx.amount:,.0f} VND - {tx.description or 'Unknown'} - {tx.merchant or ''} ({tx.category})\n"

    await update.message.reply_text(msg, parse_mode="Markdown")


async def current_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current balance."""
    if not update.message:
        return

    current_balance = get_current_balance()
    initial_balance = get_initial_balance()
    
    # Get income and expenses for breakdown
    from app.core.database import get_db_cursor
    with get_db_cursor() as cursor:
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN category = 'Income' THEN amount ELSE 0 END), 0) as income,
                COALESCE(SUM(CASE WHEN category != 'Income' THEN amount ELSE 0 END), 0) as expenses
            FROM transactions
        """)
        row = cursor.fetchone()
    
    income = row[0]
    expenses = row[1]
    
    msg = f"*Current Balance:* {current_balance:,.0f} VND\n\n"
    msg += "*Breakdown:*\n"
    msg += f"  • Initial: {initial_balance:,.0f} VND\n"
    msg += f"  • Income: +{income:,.0f} VND\n"
    msg += f"  • Expenses: -{expenses:,.0f} VND\n"

    await update.message.reply_text(msg, parse_mode="Markdown")


async def setbalance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set initial balance."""
    if not update.message:
        return

    text = update.message.text.strip()
    parts = text.split()
    
    if len(parts) < 2:
        current = get_initial_balance()
        msg = f"*Current initial balance:* {current:,.0f} VND\n\n"
        msg += "Usage: `/setbalance <amount>`"
        await update.message.reply_text(msg, parse_mode="Markdown")
        return
    
    try:
        amount = float(parts[1].replace(",", ""))
        set_initial_balance(amount)
        await update.message.reply_text(
            f"*Initial balance set to:* {amount:,.0f} VND",
            parse_mode="Markdown",
        )
    except ValueError:
        await update.message.reply_text("*Invalid amount.*")


async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove one or more transactions by ID."""
    if not update.message:
        return

    text = update.message.text.strip()
    parts = text.split()

    # If no ID provided, show recent transactions
    if len(parts) < 2:
        recent_txs = get_transactions(10)

        if not recent_txs:
            await update.message.reply_text("*No transactions to remove.*")
            return

        msg = "*Recent transactions (use /remove <id> [id2] [id3]):*\n\n"
        for tx in recent_txs[:5]:
            msg += f"• `{tx.id}` {tx.date} - {tx.amount:,.0f} VND - {tx.merchant or 'Unknown'}\n"

        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # Parse all IDs
    deleted = []
    not_found = []

    for id_str in parts[1:]:
        try:
            tx_id = int(id_str)
        except ValueError:
            not_found.append(id_str)
            continue

        tx = get_transaction(tx_id)
        if tx:
            delete_transaction(tx_id)
            deleted.append((tx_id, tx))
        else:
            not_found.append(str(tx_id))

    # Send result
    if deleted:
        msg = f"*Deleted {len(deleted)} transaction(s):*\n"
        for tx_id, tx in deleted:
            msg += f"• `{tx_id}` - {tx.amount:,.0f} VND - {tx.merchant or 'Unknown'}\n"
    else:
        msg = "*No transactions were deleted.*"

    if not_found:
        msg += f"\n*Not found:* {', '.join(not_found)}"

    await update.message.reply_text(msg, parse_mode="Markdown")


async def get_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get the current chat ID."""
    if not update.message:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else "Unknown"

    msg = f"*Chat Information:*\n\n"
    msg += f"• Chat ID: `{chat_id}`\n"
    msg += f"• User ID: `{user_id}`\n"
    msg += f"• Chat type: `{update.effective_chat.type}`"

    await update.message.reply_text(msg, parse_mode="Markdown")


def register_finance_handlers(application) -> None:
    """Register finance module handlers with the application."""
    from telegram.ext import (
        CallbackQueryHandler,
        CommandHandler,
        MessageHandler,
        filters,
    )

    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(CommandHandler("help", handle_help))
    application.add_handler(CommandHandler("month", month_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("review", review_command))
    application.add_handler(CommandHandler("edit", handle_edit))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("remove", remove_command))
    application.add_handler(CommandHandler("getId", get_id_command))
    application.add_handler(CommandHandler("current", current_command))
    application.add_handler(CommandHandler("setbalance", setbalance_command))

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.PDF, handle_document))

    application.add_handler(CallbackQueryHandler(button_callback))

