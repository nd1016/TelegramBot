"""FastAPI backend shared by verifier and reward bots."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from telegram import Bot
from telegram.error import BadRequest, Forbidden

from shared.config import get_settings
from shared.database import Base, engine, get_db
from shared.models import (
    ReferralEvent,
    ReferralLink,
    Reward,
    RewardStatus,
    RewardType,
    User,
    Verification,
    VerificationStatus,
)
from shared.schemas import (
    ClaimRewardResponse,
    CreateReferralLinkRequest,
    CreateReferralLinkResponse,
    DashboardResponse,
    RecordJoinEventRequest,
    VerifyMembershipRequest,
    VerifyMembershipResponse,
)

settings = get_settings()
logger = logging.getLogger(__name__)

app = FastAPI(title="Telegram Reward Backend")
BOT_CACHE: dict[str, Bot] = {}


def _auto_migrate_telegram_user_id_to_bigint() -> None:
    """Best-effort migration for existing PostgreSQL schemas using INTEGER IDs."""
    try:
        with engine.begin() as conn:
            data_type = conn.execute(
                text(
                    """
                    SELECT data_type
                    FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'telegram_user_id'
                    """
                )
            ).scalar_one_or_none()

            if data_type == "integer":
                conn.execute(text("ALTER TABLE users ALTER COLUMN telegram_user_id TYPE BIGINT"))
                logger.info("Auto-migrated users.telegram_user_id from INTEGER to BIGINT")
    except Exception:
        logger.exception("Failed auto-migrating users.telegram_user_id to BIGINT")


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    _auto_migrate_telegram_user_id_to_bigint()


def _get_or_create_user(db: Session, telegram_user_id: int, username: str | None, first_name: str | None) -> User:
    user = db.scalar(select(User).where(User.telegram_user_id == telegram_user_id))
    if user:
        user.username = username
        user.first_name = first_name
        return user

    user = User(
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        is_verified=False,
    )
    db.add(user)
    db.flush()
    return user


def _get_bot(bot_token: str) -> Bot:
    bot = BOT_CACHE.get(bot_token)
    if bot is None:
        bot = Bot(token=bot_token)
        BOT_CACHE[bot_token] = bot
    return bot


async def _is_member(bot_token: str, chat_id: str, user_id: int) -> bool:
    bot = _get_bot(bot_token)
    member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
    return member.status in {"member", "administrator", "creator", "restricted"}


@app.post("/verify-membership", response_model=VerifyMembershipResponse)
async def verify_membership(payload: VerifyMembershipRequest, db: Session = Depends(get_db)) -> VerifyMembershipResponse:
    user = _get_or_create_user(db, payload.telegram_user_id, payload.username, payload.first_name)

    missing: list[str] = []

    try:
        in_channel = await _is_member(settings.verifier_bot_token, settings.target_channel_id, payload.telegram_user_id)
    except (BadRequest, Forbidden) as exc:
        logger.warning("Channel membership check failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=(
                "Channel check failed (chat not found/forbidden). "
                "Verify TARGET_CHANNEL_ID format and add Verifier Bot to the channel."
            ),
        ) from exc
    except Exception as exc:
        logger.warning("Channel membership check unexpected failure: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Channel check failed due to a temporary backend error.",
        ) from exc

    try:
        in_group = await _is_member(settings.verifier_bot_token, settings.target_group_id, payload.telegram_user_id)
    except (BadRequest, Forbidden) as exc:
        logger.warning("Group membership check failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=(
                "Group check failed (chat not found/forbidden). "
                "Verify TARGET_GROUP_ID format and add Verifier Bot to the group."
            ),
        ) from exc
    except Exception as exc:
        logger.warning("Group membership check unexpected failure: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Group check failed due to a temporary backend error.",
        ) from exc

    if not in_channel:
        missing.append("channel")
    if not in_group:
        missing.append("group")

    verification = db.scalar(select(Verification).where(Verification.user_id == user.id))
    if verification is None:
        verification = Verification(user_id=user.id)
        db.add(verification)

    verification.checked_channel = in_channel
    verification.checked_group = in_group
    verification.last_checked_at = datetime.utcnow()

    just_verified = False
    if not missing:
        just_verified = not user.is_verified
        user.is_verified = True
        verification.status = VerificationStatus.verified
    else:
        verification.status = VerificationStatus.failed

    if just_verified:
        db.add(
            Reward(
                user_id=user.id,
                reward_type=RewardType.verification,
                status=RewardStatus.pending,
                amount=settings.verification_reward_amount,
                source_user_id=None,
            )
        )

        referral_event = db.scalar(select(ReferralEvent).where(ReferralEvent.invited_user_id == user.id))
        if referral_event and referral_event.status == RewardStatus.pending and referral_event.inviter_user_id != user.id:
            referral_event.status = RewardStatus.approved
            referral_event.verified_at = datetime.utcnow()

            existing_ref_reward = db.scalar(
                select(Reward).where(
                    Reward.user_id == referral_event.inviter_user_id,
                    Reward.reward_type == RewardType.referral,
                    Reward.source_user_id == user.id,
                )
            )
            if existing_ref_reward is None:
                db.add(
                    Reward(
                        user_id=referral_event.inviter_user_id,
                        reward_type=RewardType.referral,
                        status=RewardStatus.pending,
                        amount=settings.referral_reward_amount,
                        source_user_id=user.id,
                    )
                )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate reward attempt detected.") from exc

    return VerifyMembershipResponse(verified=len(missing) == 0, missing_items=missing)


@app.post("/referral-links/create", response_model=CreateReferralLinkResponse)
async def create_referral_link(payload: CreateReferralLinkRequest, db: Session = Depends(get_db)) -> CreateReferralLinkResponse:
    user = db.scalar(select(User).where(User.telegram_user_id == payload.telegram_user_id))
    if not user or not user.is_verified:
        raise HTTPException(status_code=403, detail="User is not verified.")

    existing = db.scalar(select(ReferralLink).where(ReferralLink.user_id == user.id))
    if existing:
        return CreateReferralLinkResponse(invite_link=existing.invite_link)

    code = secrets.token_urlsafe(8)
    bot = _get_bot(settings.reward_bot_token)
    telegram_link = await bot.create_chat_invite_link(
        chat_id=settings.target_group_id,
        name=f"ref-{user.telegram_user_id}",
    )

    link = ReferralLink(user_id=user.id, code=code, invite_link=telegram_link.invite_link)
    db.add(link)
    db.commit()

    return CreateReferralLinkResponse(invite_link=link.invite_link)


@app.post("/referral-events/record")
def record_join_event(payload: RecordJoinEventRequest, db: Session = Depends(get_db)) -> dict:
    invited_user = _get_or_create_user(
        db,
        telegram_user_id=payload.invited_telegram_user_id,
        username=payload.invited_username,
        first_name=payload.invited_first_name,
    )

    ref_link = db.scalar(select(ReferralLink).where(ReferralLink.invite_link == payload.invite_link))
    if ref_link is None:
        db.commit()
        return {"recorded": False, "reason": "unknown_invite_link"}

    if ref_link.user_id == invited_user.id:
        db.commit()
        return {"recorded": False, "reason": "self_referral"}

    existing_event = db.scalar(select(ReferralEvent).where(ReferralEvent.invited_user_id == invited_user.id))
    if existing_event:
        db.commit()
        return {"recorded": False, "reason": "duplicate_invited_user"}

    db.add(
        ReferralEvent(
            inviter_user_id=ref_link.user_id,
            invited_user_id=invited_user.id,
            referral_link_id=ref_link.id,
            status=RewardStatus.pending,
        )
    )
    db.commit()
    return {"recorded": True}


@app.get("/dashboard/{telegram_user_id}", response_model=DashboardResponse)
def get_dashboard(telegram_user_id: int, db: Session = Depends(get_db)) -> DashboardResponse:
    user = db.scalar(select(User).where(User.telegram_user_id == telegram_user_id))
    if not user:
        return DashboardResponse(
            verified=False,
            reward_status="not_verified",
            referral_count=0,
            verification_reward=0,
            referral_reward=0,
            invite_link=None,
        )

    invite_link = db.scalar(select(ReferralLink.invite_link).where(ReferralLink.user_id == user.id))

    referral_count = db.scalar(
        select(func.count(ReferralEvent.id)).where(
            ReferralEvent.inviter_user_id == user.id,
            ReferralEvent.status == RewardStatus.approved,
        )
    ) or 0

    verification_reward = db.scalar(
        select(func.coalesce(func.sum(Reward.amount), 0)).where(
            Reward.user_id == user.id,
            Reward.reward_type == RewardType.verification,
        )
    ) or 0

    referral_reward = db.scalar(
        select(func.coalesce(func.sum(Reward.amount), 0)).where(
            Reward.user_id == user.id,
            Reward.reward_type == RewardType.referral,
        )
    ) or 0

    pending_count = db.scalar(
        select(func.count(Reward.id)).where(Reward.user_id == user.id, Reward.status == RewardStatus.pending)
    ) or 0

    status = "pending" if pending_count > 0 else "approved"
    if user.fraud_flag:
        status = "rejected"

    return DashboardResponse(
        verified=user.is_verified,
        reward_status=status,
        referral_count=int(referral_count),
        verification_reward=float(verification_reward),
        referral_reward=float(referral_reward),
        invite_link=invite_link,
    )


@app.post("/rewards/{telegram_user_id}/claim", response_model=ClaimRewardResponse)
def claim_reward_status(telegram_user_id: int, db: Session = Depends(get_db)) -> ClaimRewardResponse:
    user = db.scalar(select(User).where(User.telegram_user_id == telegram_user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    rewards = db.scalars(select(Reward).where(Reward.user_id == user.id, Reward.status == RewardStatus.pending)).all()
    approved_count = 0

    for reward in rewards:
        if user.fraud_flag:
            reward.status = RewardStatus.rejected
        else:
            reward.status = RewardStatus.approved
            approved_count += 1

    db.commit()
    return ClaimRewardResponse(approved_count=approved_count)