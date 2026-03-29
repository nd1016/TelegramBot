"""Reward bot entrypoint - Simplified Single-Page Hub using Message Editing & Hard Refreshes."""

from __future__ import annotations

import html
import logging
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ChatMemberHandler, ContextTypes
from telegram.error import BadRequest

from reward_bot.api_client import BackendClient
from shared.config import get_settings
from shared.logging_utils import setup_logging

settings = get_settings()
logger = logging.getLogger(__name__)

# Action Constants
CB_REFRESH = "reward:refresh"

def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh Hub", callback_data=CB_REFRESH)],
        [InlineKeyboardButton("⬅️ Back to Verifier Dashboard", url=settings.verifier_bot_url)]
    ])

def _dashboard_text(dashboard: dict) -> str:
    raw_invite = dashboard.get("invite_link")
    if raw_invite:
        link_display = f"<code>{html.escape(raw_invite)}</code>"
    else:
        link_display = "<i>Tap '🔄 Refresh Hub' to generate!</i>"

    is_verified = dashboard.get("verified", False)
    verified_text = "✅ Verified Active" if is_verified else "⚠️ Unverified"
    
    v_reward = dashboard.get("verification_reward", 0)
    r_reward = dashboard.get("referral_reward", 0)
    total_coins = v_reward + r_reward
    
    try:
        return settings.reward_dashboard_text.format(
            total_coins=total_coins,
            verified_text=verified_text,
            referral_count=dashboard.get('referral_count', 0),
            pending_rewards=dashboard.get('pending_rewards', 0),
            link_display=link_display,
            last_updated=time.strftime('%H:%M:%S')
        )
    except KeyError as e:
        logger.error(f"Missing variable in REWARD_DASHBOARD_TEXT: {e}")
        return "⚠️ Error formatting dashboard text. Check your .env file variables."

async def _fetch_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict:
    user = update.effective_user
    client: BackendClient = context.application.bot_data["backend_client"]

    dashboard = await client.get_dashboard(user.id)
    
    if dashboard.get("verified") and not dashboard.get("invite_link"):
        try:
            link_result = await client.create_link(user.id)
            dashboard["invite_link"] = link_result["invite_link"]
        except Exception as e:
            logger.error(f"Failed to create invite link: {e}")
            dashboard["invite_link"] = "⚠️ ERROR: Make Reward Bot an Admin with 'Invite via Link' permission!"
            
    return dashboard

async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE, send_new: bool = False) -> None:
    query = update.callback_query
    
    try:
        dashboard = await _fetch_dashboard(update, context)
    except Exception as e:
        logger.error(f"Backend error: {e}")
        if query:
            await query.answer("🚨 Server error. Is the backend running?", show_alert=True)
        else:
            await update.effective_message.reply_text("🚨 Server error. Is the backend running?")
        return

    text = _dashboard_text(dashboard)
    keyboard = _main_keyboard()

    # THE "HARD REFRESH" LOGIC: Delete the old message and send a completely new one
    if send_new and query and query.message:
        try:
            await query.message.delete()
        except BadRequest:
            pass # Ignore if the message is too old to delete
            
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=text, 
            reply_markup=keyboard, 
            parse_mode=ParseMode.HTML, 
            disable_web_page_preview=True
        )
        return

    # Normal logic (used when typing /start)
    if query and query.message:
        try:
            await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                logger.exception("Failed to edit message")
    elif update.effective_message:
        await update.effective_message.reply_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def reward_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    
    try:
        await query.answer()
    except Exception:
        pass 

    if query.data == CB_REFRESH:
        # We tell show_dashboard to do a "Hard Refresh" by passing send_new=True
        await show_dashboard(update, context, send_new=True)

async def track_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Correctly intercepts hidden invite link data when a user joins."""
    chat_member_update = update.chat_member
    if not chat_member_update:
        return

    # Extract the exact unique link they used to join
    invite_link_obj = chat_member_update.invite_link
    if not invite_link_obj:
        return

    member = chat_member_update.new_chat_member.user
    if settings.ignore_bots and member.is_bot:
        return

    # Only trigger when they actually become a member
    new_status = chat_member_update.new_chat_member.status
    if new_status not in ["member", "restricted"]:
        return

    client: BackendClient = context.application.bot_data["backend_client"]

    try:
        await client.record_join_event(
            invited_telegram_user_id=member.id,
            invited_username=member.username,
            invited_first_name=member.first_name,
            invite_link=invite_link_obj.invite_link,
        )
        logger.info(f"✅ Successfully recorded referral for user {member.id}")
    except Exception as e:
        logger.exception(f"❌ Failed recording referral event for user={member.id}. Error: {e}")

def main() -> None:
    setup_logging(settings.log_level)
    app = Application.builder().token(settings.reward_bot_token).build()
    app.bot_data["backend_client"] = BackendClient(f"http://{settings.backend_host}:{settings.backend_port}")

    app.add_handler(CommandHandler("start", show_dashboard))
    app.add_handler(CallbackQueryHandler(reward_callback_router))
    app.add_handler(ChatMemberHandler(track_join, ChatMemberHandler.CHAT_MEMBER))
    
    logger.info("Reward bot started")
    
    # THE CRITICAL FIX: We must explicitly ask Telegram to send us 'chat_member' updates!
    app.run_polling(drop_pending_updates=True, allowed_updates=["message", "callback_query", "chat_member"])

if __name__ == "__main__":
    main()