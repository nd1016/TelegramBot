"""Welcome bot entrypoint."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from shared.config import get_settings
from shared.logging_utils import setup_logging

settings = get_settings()
logger = logging.getLogger(__name__)

async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.new_chat_members:
        return

    for member in update.message.new_chat_members:
        # Ignore other bots joining the chat
        if member.is_bot and settings.ignore_bots:
            continue

        chat_title = update.message.chat.title or "our community"
        first_name = member.first_name or "there"
        username = f"@{member.username}" if member.username else first_name

        # Format the welcome text using settings
        text = settings.welcome_message_text.format(
            first_name=first_name,
            username=username,
            chat_title=chat_title
        )

        # Build keyboard with ONLY the Verifier and Reward links (Removed the rules button)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Verify Here First", url=settings.verifier_bot_url)],
            [InlineKeyboardButton("🎁 Check Your Rewards", url=settings.reward_bot_url)]
        ])

        try:
            await update.message.reply_text(
                text=text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception:
            logger.exception("Failed to send welcome message")

def main() -> None:
    setup_logging(settings.log_level)
    app = Application.builder().token(settings.welcome_bot_token).build()

    # Listen for new chat members
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_members))

    logger.info("Welcome bot started")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()