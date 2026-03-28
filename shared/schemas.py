"""Pydantic API schemas."""

from __future__ import annotations

from pydantic import BaseModel


class VerifyMembershipRequest(BaseModel):
    telegram_user_id: int
    username: str | None = None
    first_name: str | None = None


class VerifyMembershipResponse(BaseModel):
    verified: bool
    missing_items: list[str]


class CreateReferralLinkRequest(BaseModel):
    telegram_user_id: int


class CreateReferralLinkResponse(BaseModel):
    invite_link: str


class RecordJoinEventRequest(BaseModel):
    invited_telegram_user_id: int
    invited_username: str | None = None
    invited_first_name: str | None = None
    invite_link: str


class DashboardResponse(BaseModel):
    verified: bool
    reward_status: str
    referral_count: int
    verification_reward: float
    referral_reward: float
    invite_link: str | None


class ClaimRewardResponse(BaseModel):
    approved_count: int