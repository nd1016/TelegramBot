"""Reward bot entrypoint with Telegram-native dashboard UX."""

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
from shared.telegram_ui import bool_badge

settings = get_settings()
logger = logging.getLogger(__name__)

CB_REFRESH = "reward:refresh"
CB_REWARDS = "reward:rewards"
CB_LINK = "reward:link"
CB_HOW = "reward:how"
CB_CLAIM = "reward:claim"
CB_BACK = "reward:back"


def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data=CB_REFRESH),
                InlineKeyboardButton("💰 My Rewards", callback_data=CB_REWARDS),
            ],
            [
                InlineKeyboardButton("🔗 My Referral Link", callback_data=CB_LINK),
                InlineKeyboardButton("🧭 How It Works", callback_data=CB_HOW),
            ],
            [InlineKeyboardButton("🧾 Claim Status", callback_data=CB_CLAIM)],
        ]
    )


def _back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Dashboard", callback_data=CB_BACK)]])


def _safe_reward_status(status: str) -> str:
    mapping = {
        "pending": "⏳ Pending",
        "approved": "✅ Approved",
        "rejected": "❌ Rejected",
        "not_verified": "⚠️ Not Verified",
    }
    return mapping.get(status, status)


def _dashboard_text(dashboard: dict) -> str:
    invite_link = dashboard.get("invite_link") or "Not created yet"
    verified_badge = bool_badge(dashboard.get("verified", False))

    return settings.reward_dashboard_text.format(
        verified_badge=verified_badge,
        reward_status=_safe_reward_status(dashboard.get("reward_status", "pending")),
        referral_count=dashboard.get("referral_count", 0),
        invite_link=html.escape(invite_link),
        pending_rewards=dashboard.get("pending_rewards", 0),
        approved_rewards=dashboard.get("approved_rewards", 0),
        rejected_rewards=dashboard.get("rejected_rewards", 0),
    )


def _rewards_panel_text(dashboard: dict) -> str:
    verification_total = dashboard.get("verification_reward", 0)
    referral_total = dashboard.get("referral_reward", 0)
    total_value = verification_total + referral_total

    return (
        "💰 <b>My Rewards</b>\n"
        f"• Verification rewards total: <b>{verification_total}</b>\n"
        f"• Referral rewards total: <b>{referral_total}</b>\n"
        f"• Overall value: <b>{total_value}</b>\n\n"
        "<b>Status counts</b>\n"
        f"⏳ Pending: {dashboard.get('pending_rewards', 0)}\n"
        f"✅ Approved: {dashboard.get('approved_rewards', 0)}\n"
        f"❌ Rejected: {dashboard.get('rejected_rewards', 0)}"
    )


def _referral_panel_text(dashboard: dict) -> str:
    link = dashboard.get("invite_link") or "Invite link not available yet. Tap Refresh."
    return (
        "🔗 <b>My Referral Link</b>\n"
        f"<code>{html.escape(link)}</code>\n\n"
        f"👥 Approved referrals: <b>{dashboard.get('referral_count', 0)}</b>"
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
            logger.exception("Failed to create invite link")
    return dashboard


async def _show_panel(update: Update, text: str, keyboard: InlineKeyboardMarkup) -> None:
    query = update.callback_query
    if query and query.message:
        try:
            await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
            return
        except Exception:
            logger.exception("Failed editing reward dashboard message")

    if update.effective_message:
        await update.effective_message.reply_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        dashboard = await _fetch_dashboard(update, context)
    except Exception:
        logger.exception("Failed to fetch dashboard")
        await _show_panel(
            update,
            "⚠️ Temporary error loading your dashboard. Please tap Refresh.",
            _main_keyboard(),
        )
        return

    if not dashboard.get("verified"):
        await _show_panel(update, settings.reward_not_verified_text, _main_keyboard())
        return

    await _show_panel(update, _dashboard_text(dashboard), _main_keyboard())


async def claim_from_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    client: BackendClient = context.application.bot_data["backend_client"]

    try:
        result = await client.claim(user.id)
    except Exception:
        logger.exception("Failed claim from dashboard")
        await query.answer("Claim failed. Try again shortly.", show_alert=True)
        return

    await query.answer(settings.reward_claim_result_text.format(approved_count=result.get("approved_count", 0)))
    await show_dashboard(update, context)


async def show_rewards_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    dashboard = await _fetch_dashboard(update, context)
    await _show_panel(update, _rewards_panel_text(dashboard), _back_keyboard())


async def show_referral_link_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    dashboard = await _fetch_dashboard(update, context)
    await _show_panel(update, _referral_panel_text(dashboard), _back_keyboard())


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
    elif action == CB_REWARDS:
        await show_rewards_panel(update, context)
    elif action == CB_LINK:
        await show_referral_link_panel(update, context)
    elif action == CB_HOW:
        await show_how_it_works(update, context)
    elif action == CB_CLAIM:
        await claim_from_panel(update, context)


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

    app.add_handler(CommandHandler("start", show_dashboard))
    app.add_handler(CommandHandler("claim", claim))
    app.add_handler(CallbackQueryHandler(reward_callback_router, pattern=r"^reward:"))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, track_join))
    app.add_error_handler(on_error)

    logger.info("Reward bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
