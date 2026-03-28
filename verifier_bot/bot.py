"""Verifier bot entrypoint."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from shared.config import get_settings
from shared.logging_utils import setup_logging
from verifier_bot.api_client import BackendClient

settings = get_settings()
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Join Channel", url=settings.channel_join_url)],
            [InlineKeyboardButton("Join Group", url=settings.group_join_url)],
            [InlineKeyboardButton("Verify", callback_data="verify_membership")],
        ]
    )
    await update.effective_message.reply_text(settings.verifier_start_text, reply_markup=keyboard)


async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user = query.from_user
    client: BackendClient = context.application.bot_data["backend_client"]

    try:
        result = await client.verify_membership(
            telegram_user_id=user.id,
            username=user.username,
            first_name=user.first_name,
        )
    except Exception:
        logger.warning("Verification request failed", exc_info=True)
        await query.message.reply_text("Temporary error. Please try again in a minute.")
        return

    if result.get("backend_error"):
        await query.message.reply_text(f"⚠️ {result['backend_error']}")
        return

    if result.get("verified"):
        await query.message.reply_text(settings.verifier_verify_success_text)
    else:
        missing_items = ", ".join(result.get("missing_items", [])) or "unknown"
        await query.message.reply_text(settings.verifier_verify_fail_text.format(missing_items=missing_items))


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled verifier bot error update=%s", update, exc_info=context.error)


def main() -> None:
    setup_logging(settings.log_level)

    app = Application.builder().token(settings.verifier_bot_token).build()
    app.bot_data["backend_client"] = BackendClient(
        f"http://{settings.backend_host}:{settings.backend_port}"
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(verify_callback, pattern="^verify_membership$"))
    app.add_error_handler(on_error)

    logger.info("Verifier bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()