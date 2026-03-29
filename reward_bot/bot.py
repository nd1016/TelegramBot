"""Reward bot entrypoint with simple Telegram-native dashboard UX."""

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

from reward_bot.api_client import BackendClient
from shared.config import get_settings
from shared.logging_utils import setup_logging

settings = get_settings()
logger = logging.getLogger(__name__)

CB_REFRESH = "reward:refresh"
CB_REWARDS = "reward:rewards"
CB_LINK = "reward:link"
CB_HOW = "reward:how"
CB_BACK = "reward:back"


def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(settings.reward_btn_refresh, callback_data=CB_REFRESH),
                InlineKeyboardButton(settings.reward_btn_my_rewards, callback_data=CB_REWARDS),
            ],
            [
                InlineKeyboardButton(settings.reward_btn_referral_link, callback_data=CB_LINK),
                InlineKeyboardButton(settings.reward_btn_how_it_works, callback_data=CB_HOW),
            ],
        ]
    )


def _back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(settings.reward_btn_back_dashboard, callback_data=CB_BACK)]])


def _friendly_verification_status(verified: bool) -> str:
    return "✅ Verified" if verified else "❌ Not Verified"


def _friendly_verification_reward_status(verification_reward_total: float) -> str:
    return "✅ Verification Reward Earned" if verification_reward_total > 0 else "❌ Verification Reward Not Earned"


def _friendly_referral_reward_status(referral_reward_total: float) -> str:
    return "✅ Referral Reward Earned" if referral_reward_total > 0 else "❌ Referral Reward Not Earned"


def _dashboard_text(dashboard: dict) -> str:
    verified = dashboard.get("verified", False)
    verification_reward = float(dashboard.get("verification_reward", 0))
    referral_reward = float(dashboard.get("referral_reward", 0))
    referral_count = int(dashboard.get("referral_count", 0))
    pending_rewards = int(dashboard.get("pending_rewards", 0))

    invite_link = dashboard.get("invite_link") or "Not available yet. Tap Refresh."
    pending_line = f"\n⏳ Pending Review: {pending_rewards}" if pending_rewards > 0 else ""

    return (
        "🎁 <b>Reward Dashboard</b>\n"
        f"{_friendly_verification_status(verified)}\n"
        f"{_friendly_verification_reward_status(verification_reward)}\n"
        f"{_friendly_referral_reward_status(referral_reward)}\n"
        f"👥 Total Referrals: <b>{referral_count}</b>\n"
        f"🔗 Invite Link: <code>{html.escape(invite_link)}</code>"
        f"{pending_line}"
    )


def _my_rewards_text(dashboard: dict) -> str:
    verification_reward = float(dashboard.get("verification_reward", 0))
    referral_reward = float(dashboard.get("referral_reward", 0))
    total = verification_reward + referral_reward

    return (
        "💰 <b>My Rewards</b>\n"
        f"• Verification Reward: <b>{verification_reward}</b>\n"
        f"• Referral Reward: <b>{referral_reward}</b>\n"
        f"• Total: <b>{total}</b>"
    )


def _my_referral_link_text(dashboard: dict) -> str:
    invite_link = dashboard.get("invite_link") or "Not available yet. Tap Refresh."
    referral_count = int(dashboard.get("referral_count", 0))
    return (
        "🔗 <b>My Referral Link</b>\n"
        f"<code>{html.escape(invite_link)}</code>\n\n"
        f"👥 Total Referrals: <b>{referral_count}</b>"
    )


async def _fetch_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict:
    user = update.effective_user
    client: BackendClient = context.application.bot_data["backend_client"]

    dashboard = await client.get_dashboard(user.id)

    if dashboard.get("verified") and not dashboard.get("invite_link"):
        try:
            link_result = await client.create_link(user.id)
            dashboard["invite_link"] = link_result["invite_link"]
        except Exception:
            logger.exception("Failed to create referral link for user=%s", user.id)

    return dashboard


async def _show_panel(update: Update, text: str, keyboard: InlineKeyboardMarkup) -> None:
    query = update.callback_query
    if query and query.message:
        try:
            await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
            return
        except Exception:
            logger.exception("Failed editing reward bot panel")

    if update.effective_message:
        await update.effective_message.reply_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        dashboard = await _fetch_dashboard(update, context)
    except Exception:
        logger.exception("Failed to load reward dashboard")
        await _show_panel(update, "⚠️ Temporary error. Please tap Refresh.", _main_keyboard())
        return

    if not dashboard.get("verified"):
        await _show_panel(update, settings.reward_not_verified_text, _main_keyboard())
        return

    await _show_panel(update, _dashboard_text(dashboard), _main_keyboard())


async def show_my_rewards(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    dashboard = await _fetch_dashboard(update, context)
    if not dashboard.get("verified"):
        await _show_panel(update, settings.reward_not_verified_text, _main_keyboard())
        return

    await _show_panel(update, _my_rewards_text(dashboard), _back_keyboard())


async def show_my_referral_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    dashboard = await _fetch_dashboard(update, context)
    if not dashboard.get("verified"):
        await _show_panel(update, settings.reward_not_verified_text, _main_keyboard())
        return

    await _show_panel(update, _my_referral_link_text(dashboard), _back_keyboard())


async def show_how_it_works(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await _show_panel(update, settings.reward_how_it_works_text, _back_keyboard())


async def reward_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    action = query.data

    if action in {CB_REFRESH, CB_BACK}:
        await query.answer()
        await show_dashboard(update, context)
        return

    if action == CB_REWARDS:
        await show_my_rewards(update, context)
        return

    if action == CB_LINK:
        await show_my_referral_link(update, context)
        return

    if action == CB_HOW:
        await show_how_it_works(update, context)
        return

    logger.warning("Unknown reward callback action=%s", action)
    await query.answer("This button is not available right now.", show_alert=True)


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
            logger.exception("Failed recording referral join for user=%s", member.id)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled reward bot error update=%s", update, exc_info=context.error)


def main() -> None:
    setup_logging(settings.log_level)

    app = Application.builder().token(settings.reward_bot_token).build()
    app.bot_data["backend_client"] = BackendClient(
        f"http://{settings.backend_host}:{settings.backend_port}"
    )

    app.add_handler(CommandHandler("start", show_dashboard))
    app.add_handler(CallbackQueryHandler(reward_callback_router, pattern=r"^reward:"))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, track_join))
    app.add_error_handler(on_error)

    logger.info("Reward bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
