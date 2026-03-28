"""Welcome bot entrypoint."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from shared.config import get_settings
from shared.logging_utils import setup_logging
from welcome_bot.api_client import BackendClient

settings = get_settings()
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id if update.effective_chat else settings.target_group_id
    dashboard_url = f"{settings.web_dashboard_base_url}/dashboard/welcome?chat_id={chat_id}"
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("⚙️ Welcome Dashboard", url=dashboard_url)]]
    )
    await update.effective_message.reply_text(
        "Welcome bot is active ✅\nI will greet new members and can be configured from the dashboard.",
        reply_markup=keyboard,
    )


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
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, greet_new_members))
    app.add_error_handler(on_error)

    logger.info("Welcome bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
