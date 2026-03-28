"""SQLAlchemy models for reward system."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database import Base


class RewardStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class RewardType(str, enum.Enum):
    verification = "verification"
    referral = "referral"


class VerificationStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    fraud_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Verification(Base):
    __tablename__ = "verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    status: Mapped[VerificationStatus] = mapped_column(Enum(VerificationStatus), default=VerificationStatus.pending)
    checked_channel: Mapped[bool] = mapped_column(Boolean, default=False)
    checked_group: Mapped[bool] = mapped_column(Boolean, default=False)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReferralLink(Base):
    __tablename__ = "referral_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    invite_link: Mapped[str] = mapped_column(String(1024), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReferralEvent(Base):
    __tablename__ = "referral_events"
    __table_args__ = (UniqueConstraint("invited_user_id", name="uq_referral_event_invited_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inviter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    invited_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    referral_link_id: Mapped[int] = mapped_column(ForeignKey("referral_links.id"), index=True)
    status: Mapped[RewardStatus] = mapped_column(Enum(RewardStatus), default=RewardStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Reward(Base):
    __tablename__ = "rewards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reward_type: Mapped[RewardType] = mapped_column(Enum(RewardType), index=True)
    status: Mapped[RewardStatus] = mapped_column(Enum(RewardStatus), default=RewardStatus.pending)
    amount: Mapped[float] = mapped_column(Float)
    source_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "reward_type", "source_user_id", name="uq_reward_uniqueness"),
    )