"""Verifier bot entrypoint with Telegram-native dashboard UX."""

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

from shared.config import get_settings
from shared.logging_utils import setup_logging
from shared.telegram_ui import bool_badge
from verifier_bot.api_client import BackendClient

settings = get_settings()
logger = logging.getLogger(__name__)

CB_VERIFY = "verifier:verify"
CB_REFRESH = "verifier:refresh"
CB_HELP = "verifier:help"
CB_BACK = "verifier:back"


def _build_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📢 Join Channel", url=settings.channel_join_url),
                InlineKeyboardButton("👥 Join Group", url=settings.group_join_url),
            ],
            [
                InlineKeyboardButton("✅ Verify Now", callback_data=CB_VERIFY),
                InlineKeyboardButton("🔄 Refresh Status", callback_data=CB_REFRESH),
            ],
            [InlineKeyboardButton("ℹ️ Help", callback_data=CB_HELP)],
        ]
    )


def _build_help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=CB_BACK)]])


def _build_dashboard_text(verification: dict) -> str:
    missing_items = set(verification.get("missing_items", []))
    is_verified = verification.get("verified", False)

    channel_ok = "channel" not in missing_items
    group_ok = "group" not in missing_items

    return (
        f"{settings.verifier_start_text}\n\n"
        f"<b>Progress</b>\n"
        f"• Channel joined: {bool_badge(channel_ok)}\n"
        f"• Group joined: {bool_badge(group_ok)}\n"
        f"• Verified: {bool_badge(is_verified)}\n\n"
        f"Tap <b>Verify Now</b> after joining both destinations."
    )


async def _fetch_verification_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict:
    user = update.effective_user
    client: BackendClient = context.application.bot_data["backend_client"]
    result = await client.verify_membership(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
    )
    return result


async def _render_or_edit_panel(
    update: Update,
    text: str,
    keyboard: InlineKeyboardMarkup,
) -> None:
    query = update.callback_query
    if query and query.message:
        try:
            await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
            return
        except Exception:
            logger.exception("Failed editing verifier dashboard message")

    if update.effective_message:
        await update.effective_message.reply_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        result = await _fetch_verification_status(update, context)
    except Exception:
        logger.warning("Verification status fetch failed", exc_info=True)
        await _render_or_edit_panel(
            update,
            "⚠️ Verification service is temporarily unavailable. Please tap Refresh Status shortly.",
            _build_main_keyboard(),
        )
        return

    if result.get("backend_error"):
        await _render_or_edit_panel(update, f"⚠️ {result['backend_error']}", _build_main_keyboard())
        return

    await _render_or_edit_panel(update, _build_dashboard_text(result), _build_main_keyboard())


async def verify_or_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await start(update, context)


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await _render_or_edit_panel(update, settings.verifier_help_text, _build_help_keyboard())


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled verifier bot error update=%s", update, exc_info=context.error)


def main() -> None:
    setup_logging(settings.log_level)

    app = Application.builder().token(settings.verifier_bot_token).build()
    app.bot_data["backend_client"] = BackendClient(
        f"http://{settings.backend_host}:{settings.backend_port}"
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(verify_or_refresh, pattern=f"^({CB_VERIFY}|{CB_REFRESH}|{CB_BACK})$"))
    app.add_handler(CallbackQueryHandler(show_help, pattern=f"^{CB_HELP}$"))
    app.add_error_handler(on_error)

    logger.info("Verifier bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
