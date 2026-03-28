"""Shared application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _to_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_multiline(value: str) -> str:
    """Allow using \n inside .env values for multiline Telegram text."""
    return value.replace("\\n", "\n")


@dataclass(frozen=True)
class Settings:
    database_url: str
    backend_host: str
    backend_port: int

    verifier_bot_token: str
    reward_bot_token: str
    welcome_bot_token: str

    target_channel_id: str
    target_group_id: str
    channel_join_url: str
    group_join_url: str

    referral_reward_amount: float
    verification_reward_amount: float

    verifier_start_text: str
    verifier_verify_success_text: str
    verifier_verify_fail_text: str
    verifier_help_text: str
    verifier_btn_join_channel: str
    verifier_btn_join_group: str
    verifier_btn_verify_now: str
    verifier_btn_refresh_status: str
    verifier_btn_help: str
    verifier_btn_back: str

    reward_not_verified_text: str
    reward_dashboard_text: str
    reward_claim_result_text: str
    reward_how_it_works_text: str
    reward_btn_refresh: str
    reward_btn_my_rewards: str
    reward_btn_referral_link: str
    reward_btn_how_it_works: str
    reward_btn_claim_status: str
    reward_btn_back_dashboard: str

    welcome_message_text: str
    welcome_button_text: str
    welcome_button_url: str
    welcome_start_text: str
    welcome_help_text: str
    welcome_btn_refresh: str
    welcome_btn_preview: str
    welcome_btn_help: str
    welcome_btn_back: str

    ignore_bots: bool
    log_level: str


def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/rewards_db"),
        backend_host=os.getenv("BACKEND_HOST", "0.0.0.0"),
        backend_port=int(os.getenv("BACKEND_PORT", "8000")),
        verifier_bot_token=os.getenv("VERIFIER_BOT_TOKEN", ""),
        reward_bot_token=os.getenv("REWARD_BOT_TOKEN", ""),
        welcome_bot_token=os.getenv("WELCOME_BOT_TOKEN", ""),
        target_channel_id=os.getenv("TARGET_CHANNEL_ID", ""),
        target_group_id=os.getenv("TARGET_GROUP_ID", ""),
        channel_join_url=os.getenv("CHANNEL_JOIN_URL", "https://t.me/example_channel"),
        group_join_url=os.getenv("GROUP_JOIN_URL", "https://t.me/example_group"),
        referral_reward_amount=float(os.getenv("REFERRAL_REWARD_AMOUNT", "5")),
        verification_reward_amount=float(os.getenv("VERIFICATION_REWARD_AMOUNT", "2")),
        verifier_start_text=_normalize_multiline(
            os.getenv(
                "VERIFIER_START_TEXT",
                (
                    "🔐 <b>Verification Dashboard</b>\n"
                    "Keep your access active by joining both destinations and tapping verify."
                ),
            )
        ),
        verifier_verify_success_text=_normalize_multiline(
            os.getenv(
                "VERIFIER_VERIFY_SUCCESS_TEXT",
                "✅ You are verified! Open the Reward Bot to track rewards.",
            )
        ),
        verifier_verify_fail_text=_normalize_multiline(
            os.getenv(
                "VERIFIER_VERIFY_FAIL_TEXT",
                "❌ Verification incomplete. Missing: {missing_items}.",
            )
        ),
        verifier_help_text=_normalize_multiline(
            os.getenv(
                "VERIFIER_HELP_TEXT",
                (
                    "ℹ️ <b>How verification works</b>\n"
                    "1) Join channel\n"
                    "2) Join group\n"
                    "3) Tap Verify Now\n"
                    "Use Refresh Status anytime to re-check your progress."
                ),
            )
        ),
        verifier_btn_join_channel=os.getenv("VERIFIER_BTN_JOIN_CHANNEL", "📢 Join Channel"),
        verifier_btn_join_group=os.getenv("VERIFIER_BTN_JOIN_GROUP", "👥 Join Group"),
        verifier_btn_verify_now=os.getenv("VERIFIER_BTN_VERIFY_NOW", "✅ Verify Now"),
        verifier_btn_refresh_status=os.getenv("VERIFIER_BTN_REFRESH_STATUS", "🔄 Refresh Status"),
        verifier_btn_help=os.getenv("VERIFIER_BTN_HELP", "ℹ️ Help"),
        verifier_btn_back=os.getenv("VERIFIER_BTN_BACK", "⬅️ Back"),
        reward_not_verified_text=_normalize_multiline(
            os.getenv(
                "REWARD_NOT_VERIFIED_TEXT",
                "You are not verified yet. Please complete verification in the Verifier Bot first.",
            )
        ),
        reward_dashboard_text=_normalize_multiline(
            os.getenv(
                "REWARD_DASHBOARD_TEXT",
                (
                    "🎁 <b>Rewards Dashboard</b>\n"
                    "🛡 Verification: {verified_badge}\n"
                    "📌 Reward status: <b>{reward_status}</b>\n"
                    "👥 Referrals: <b>{referral_count}</b>\n"
                    "🔗 Invite link: {invite_link}\n\n"
                    "<b>Reward Breakdown</b>\n"
                    "⏳ Pending: {pending_rewards}\n"
                    "✅ Approved: {approved_rewards}\n"
                    "❌ Rejected: {rejected_rewards}"
                ),
            )
        ),
        reward_claim_result_text=_normalize_multiline(
            os.getenv(
                "REWARD_CLAIM_RESULT_TEXT",
                "Claim request processed. {approved_count} rewards approved.",
            )
        ),
        reward_how_it_works_text=_normalize_multiline(
            os.getenv(
                "REWARD_HOW_IT_WORKS_TEXT",
                (
                    "🧭 <b>How rewards work</b>\n"
                    "• Verification reward is created when you pass membership checks.\n"
                    "• Referral rewards are added after invited users verify.\n"
                    "• Claim Status moves pending rewards to approved/rejected."
                ),
            )
        ),
        reward_btn_refresh=os.getenv("REWARD_BTN_REFRESH", "🔄 Refresh"),
        reward_btn_my_rewards=os.getenv("REWARD_BTN_MY_REWARDS", "💰 My Rewards"),
        reward_btn_referral_link=os.getenv("REWARD_BTN_REFERRAL_LINK", "🔗 My Referral Link"),
        reward_btn_how_it_works=os.getenv("REWARD_BTN_HOW_IT_WORKS", "🧭 How It Works"),
        reward_btn_claim_status=os.getenv("REWARD_BTN_CLAIM_STATUS", "🧾 Claim Status"),
        reward_btn_back_dashboard=os.getenv("REWARD_BTN_BACK_DASHBOARD", "⬅️ Back to Dashboard"),
        welcome_message_text=_normalize_multiline(
            os.getenv(
                "WELCOME_MESSAGE_TEXT",
                "👋 Welcome {first_name} to {chat_title}!\nRead the rules and enjoy your stay.",
            )
        ),
        welcome_button_text=os.getenv("WELCOME_BUTTON_TEXT", "📌 Group Rules"),
        welcome_button_url=os.getenv("WELCOME_BUTTON_URL", "https://t.me/example_group"),
        welcome_start_text=_normalize_multiline(
            os.getenv(
                "WELCOME_START_TEXT",
                (
                    "👋 <b>Welcome Bot Dashboard</b>\n"
                    "I greet new members with a polished, configurable welcome message."
                ),
            )
        ),
        welcome_help_text=_normalize_multiline(
            os.getenv(
                "WELCOME_HELP_TEXT",
                (
                    "ℹ️ <b>Welcome bot tips</b>\n"
                    "• Supports placeholders: {first_name}, {username}, {chat_title}\n"
                    "• Uses backend welcome settings per chat\n"
                    "• Ignores bot accounts when IGNORE_BOTS=true"
                ),
            )
        ),
        welcome_btn_refresh=os.getenv("WELCOME_BTN_REFRESH", "🔄 Refresh Settings"),
        welcome_btn_preview=os.getenv("WELCOME_BTN_PREVIEW", "🧪 Preview Message"),
        welcome_btn_help=os.getenv("WELCOME_BTN_HELP", "ℹ️ Help"),
        welcome_btn_back=os.getenv("WELCOME_BTN_BACK", "⬅️ Back"),
        ignore_bots=_to_bool(os.getenv("IGNORE_BOTS"), default=True),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
