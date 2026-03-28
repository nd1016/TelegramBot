"""Reward bot entrypoint."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from reward_bot.api_client import BackendClient
from shared.config import get_settings
from shared.logging_utils import setup_logging

settings = get_settings()
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    client: BackendClient = context.application.bot_data["backend_client"]

    try:
        dashboard = await client.get_dashboard(user.id)
    except Exception:
        logger.exception("Failed to fetch dashboard")
        await update.effective_message.reply_text("Temporary error. Please try again.")
        return

    if not dashboard.get("verified"):
        await update.effective_message.reply_text(settings.reward_not_verified_text)
        return

    if not dashboard.get("invite_link"):
        try:
            link_result = await client.create_link(user.id)
            dashboard["invite_link"] = link_result["invite_link"]
        except Exception:
            logger.exception("Failed to create invite link")
            dashboard["invite_link"] = "Unavailable now"

    text = settings.reward_dashboard_text.format(
        reward_status=dashboard.get("reward_status", "pending"),
        referral_count=dashboard.get("referral_count", 0),
        verification_reward=dashboard.get("verification_reward", 0),
        referral_reward=dashboard.get("referral_reward", 0),
        invite_link=dashboard.get("invite_link", "Unavailable"),
    )
    await update.effective_message.reply_text(text)


async def claim(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    client: BackendClient = context.application.bot_data["backend_client"]

    try:
        result = await client.claim(user.id)
    except Exception:
        logger.exception("Failed to claim rewards")
        await update.effective_message.reply_text("Temporary error while claiming. Please retry later.")
        return

    await update.effective_message.reply_text(
        settings.reward_claim_result_text.format(approved_count=result.get("approved_count", 0))
    )


async def track_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.new_chat_members:
        return

    if settings.ignore_bots:
        new_members = [member for member in update.message.new_chat_members if not member.is_bot]
    else:
        new_members = list(update.message.new_chat_members)

    if not new_members:
        return

    invite_link = update.message.invite_link
    if invite_link is None:
        return

    client: BackendClient = context.application.bot_data["backend_client"]

    for member in new_members:
        try:
            await client.record_join_event(
                invited_telegram_user_id=member.id,
                invited_username=member.username,
                invited_first_name=member.first_name,
                invite_link=invite_link.invite_link,
            )
        except Exception:
            logger.exception("Failed recording referral event for user=%s", member.id)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled reward bot error update=%s", update, exc_info=context.error)


def main() -> None:
    setup_logging(settings.log_level)

    app = Application.builder().token(settings.reward_bot_token).build()
    app.bot_data["backend_client"] = BackendClient(
        f"http://{settings.backend_host}:{settings.backend_port}"
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("claim", claim))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, track_join))
    app.add_error_handler(on_error)

    logger.info("Reward bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()