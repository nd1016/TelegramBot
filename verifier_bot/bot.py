"""Verifier bot entrypoint."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
from telegram.error import BadRequest

from verifier_bot.api_client import BackendClient
from shared.config import get_settings
from shared.logging_utils import setup_logging

settings = get_settings()
logger = logging.getLogger(__name__)

CB_VERIFY = "verify:check"
CB_REFRESH = "verify:refresh"

def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(settings.verifier_btn_join_channel, url=settings.channel_join_url),
            InlineKeyboardButton(settings.verifier_btn_join_group, url=settings.group_join_url)
        ],
        [InlineKeyboardButton(settings.verifier_btn_verify_now, callback_data=CB_VERIFY)],
        [InlineKeyboardButton(settings.verifier_btn_refresh_status, callback_data=CB_REFRESH)]
    ])

def _success_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎉 Claim Your Rewards!", url=settings.reward_bot_url)]
    ])

async def show_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = settings.verifier_start_text
    if update.callback_query:
        try:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text=text, reply_markup=_main_keyboard(), parse_mode=ParseMode.HTML)
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                logger.exception("Failed to edit start message")
    elif update.message:
        await update.message.reply_text(text=text, reply_markup=_main_keyboard(), parse_mode=ParseMode.HTML)

async def handle_verification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    await query.answer("Checking your membership securely...")

    client: BackendClient = context.application.bot_data.get("backend_client")
    
    try:
        # Ask the backend to verify the user and update the database
        result = await client.verify_membership(user.id, user.username, user.first_name)
        verified = result.get("verified", False)
        missing = result.get("missing_items", [])
    except Exception as e:
        logger.exception("Backend verification failed")
        await query.answer("🚨 Server error. Could not verify at this time.", show_alert=True)
        return

    if not verified:
        text = settings.verifier_verify_fail_text.format(missing_items=", ".join(missing).title())
        try:
            await query.edit_message_text(text=text, reply_markup=_main_keyboard(), parse_mode=ParseMode.HTML)
        except BadRequest:
            pass
    else:
        text = settings.verifier_verify_success_text
        try:
            await query.edit_message_text(text=text, reply_markup=_success_keyboard(), parse_mode=ParseMode.HTML)
        except BadRequest:
            pass

def main() -> None:
    setup_logging(settings.log_level)
    app = Application.builder().token(settings.verifier_bot_token).build()
    app.bot_data["backend_client"] = BackendClient(f"http://{settings.backend_host}:{settings.backend_port}")

    app.add_handler(CommandHandler("start", show_start))
    app.add_handler(CallbackQueryHandler(handle_verification, pattern=f"^{CB_VERIFY}$"))
    app.add_handler(CallbackQueryHandler(show_start, pattern=f"^{CB_REFRESH}$"))

    logger.info("Verifier bot started")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()