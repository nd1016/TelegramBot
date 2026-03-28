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

    target_channel_id: str
    target_group_id: str
    channel_join_url: str
    group_join_url: str

    referral_reward_amount: float
    verification_reward_amount: float

    verifier_start_text: str
    verifier_verify_success_text: str
    verifier_verify_fail_text: str

    reward_not_verified_text: str
    reward_dashboard_text: str
    reward_claim_result_text: str

    ignore_bots: bool
    log_level: str



def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/rewards_db"),
        backend_host=os.getenv("BACKEND_HOST", "0.0.0.0"),
        backend_port=int(os.getenv("BACKEND_PORT", "8000")),
        verifier_bot_token=os.getenv("VERIFIER_BOT_TOKEN", ""),
        reward_bot_token=os.getenv("REWARD_BOT_TOKEN", ""),
        target_channel_id=os.getenv("TARGET_CHANNEL_ID", ""),
        target_group_id=os.getenv("TARGET_GROUP_ID", ""),
        channel_join_url=os.getenv("CHANNEL_JOIN_URL", "https://t.me/example_channel"),
        group_join_url=os.getenv("GROUP_JOIN_URL", "https://t.me/example_group"),
        referral_reward_amount=float(os.getenv("REFERRAL_REWARD_AMOUNT", "5")),
        verification_reward_amount=float(os.getenv("VERIFICATION_REWARD_AMOUNT", "2")),
        verifier_start_text=_normalize_multiline(
            os.getenv(
                "VERIFIER_START_TEXT",
                "Welcome! Please join our channel and group, then tap Verify.",
            )
        ),
        verifier_verify_success_text=_normalize_multiline(
            os.getenv(
                "VERIFIER_VERIFY_SUCCESS_TEXT",
                "✅ You are verified! You can now use the Reward Bot.",
            )
        ),
        verifier_verify_fail_text=_normalize_multiline(
            os.getenv(
                "VERIFIER_VERIFY_FAIL_TEXT",
                "❌ Verification incomplete. Missing: {missing_items}.",
            )
        ),
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
                    "🎁 Reward Dashboard\n"
                    "Status: {reward_status}\n"
                    "Referral count: {referral_count}\n"
                    "Verification reward: {verification_reward}\n"
                    "Referral rewards: {referral_reward}\n"
                    "Invite link: {invite_link}"
                ),
            )
        ),
        reward_claim_result_text=_normalize_multiline(
            os.getenv(
                "REWARD_CLAIM_RESULT_TEXT",
                "Claim request processed. {approved_count} rewards approved.",
            )
        ),
        ignore_bots=_to_bool(os.getenv("IGNORE_BOTS"), default=True),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )