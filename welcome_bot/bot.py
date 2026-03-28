"""Welcome bot entrypoint with Telegram-native dashboard UX."""

from __future__ import annotations

import html
import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from shared.config import get_settings
from shared.logging_utils import setup_logging
from welcome_bot.api_client import BackendClient

settings = get_settings()
logger = logging.getLogger(__name__)

CB_REFRESH = "welcome:refresh"
CB_PREVIEW = "welcome:preview"
CB_HELP = "welcome:help"
CB_BACK = "welcome:back"


def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(settings.welcome_btn_refresh, callback_data=CB_REFRESH),
                InlineKeyboardButton(settings.welcome_btn_preview, callback_data=CB_PREVIEW),
            ],
            [InlineKeyboardButton(settings.welcome_btn_help, callback_data=CB_HELP)],
        ]
    )


def _back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(settings.welcome_btn_back, callback_data=CB_BACK)]])


def _resolve_chat_context(update: Update) -> tuple[str, str]:
    chat = update.effective_chat
    if chat:
        return str(chat.id), chat.title or "this group"
    return settings.target_group_id, "this group"


async def _fetch_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict:
    chat_id, _ = _resolve_chat_context(update)
    client: BackendClient = context.application.bot_data["backend_client"]
    try:
        return await client.get_welcome_settings(chat_id)
    except Exception:
        logger.exception("Failed to load welcome settings for chat_id=%s", chat_id)
        return {
            "chat_id": chat_id,
            "message_template": settings.welcome_message_text,
            "button_text": settings.welcome_button_text,
            "button_url": settings.welcome_button_url,
        }


def _settings_panel_text(data: dict) -> str:
    return (
        f"{settings.welcome_start_text}\n\n"
        f"<b>Active settings</b>\n"
        f"• Chat ID: <code>{html.escape(data.get('chat_id', settings.target_group_id))}</code>\n"
        f"• Button text: <b>{html.escape(data.get('button_text') or 'None')}</b>\n"
        f"• Button URL: <code>{html.escape(data.get('button_url') or 'None')}</code>\n\n"
        f"<b>Template preview</b>\n<code>{html.escape(data.get('message_template', settings.welcome_message_text))}</code>"
    )


def _render_preview(data: dict, chat_title: str) -> str:
    template = data.get("message_template") or settings.welcome_message_text
    rendered = template.format(
        first_name="New Member",
        username="@new_member",
        chat_title=chat_title,
    )
    return f"🧪 <b>Preview</b>\n{html.escape(rendered)}"


async def _show_panel(update: Update, text: str, keyboard: InlineKeyboardMarkup) -> None:
    query = update.callback_query
    if query and query.message:
        try:
            await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
            return
        except Exception:
            logger.exception("Failed editing welcome dashboard message")

    if update.effective_message:
        await update.effective_message.reply_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings_data = await _fetch_settings(update, context)
    await _show_panel(update, _settings_panel_text(settings_data), _main_keyboard())


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    action = query.data
    if action in {CB_REFRESH, CB_BACK}:
        await start(update, context)
        return

    if action == CB_HELP:
        await _show_panel(update, settings.welcome_help_text, _back_keyboard())
        return

    if action == CB_PREVIEW:
        settings_data = await _fetch_settings(update, context)
        _, chat_title = _resolve_chat_context(update)
        await _show_panel(update, _render_preview(settings_data, chat_title), _back_keyboard())
        return

    await query.answer("This action is not available yet.", show_alert=True)


async def greet_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.new_chat_members:
        return

    if settings.ignore_bots:
        new_members = [member for member in update.message.new_chat_members if not member.is_bot]
    else:
        new_members = list(update.message.new_chat_members)

    if not new_members:
        return

    chat = update.effective_chat
    chat_id = str(chat.id if chat else settings.target_group_id)
    chat_title = chat.title if chat and chat.title else "this group"

    client: BackendClient = context.application.bot_data["backend_client"]
    try:
        welcome_settings = await client.get_welcome_settings(chat_id)
    except Exception:
        logger.exception("Failed to load welcome settings for chat_id=%s", chat_id)
        welcome_settings = {
            "message_template": settings.welcome_message_text,
            "button_text": settings.welcome_button_text,
            "button_url": settings.welcome_button_url,
        }

    for member in new_members:
        message_text = welcome_settings.get("message_template") or settings.welcome_message_text
        message_text = message_text.format(
            first_name=member.first_name or "there",
            username=(f"@{member.username}" if member.username else "no_username"),
            chat_title=chat_title,
        )

        button_text = welcome_settings.get("button_text")
        button_url = welcome_settings.get("button_url")
        reply_markup = None
        if button_text and button_url:
            reply_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton(button_text, url=button_url)]]
            )

        await update.effective_message.reply_text(message_text, reply_markup=reply_markup)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled welcome bot error update=%s", update, exc_info=context.error)


def main() -> None:
    setup_logging(settings.log_level)

    app = Application.builder().token(settings.welcome_bot_token).build()
    app.bot_data["backend_client"] = BackendClient(
        f"http://{settings.backend_host}:{settings.backend_port}"
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_router, pattern=r"^welcome:"))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, greet_new_members))
    app.add_error_handler(on_error)

    logger.info("Welcome bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
