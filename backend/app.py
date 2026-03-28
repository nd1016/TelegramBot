"""FastAPI backend shared by verifier, reward, and welcome bots."""

from __future__ import annotations

import html
import logging
import secrets
from datetime import datetime
from urllib.parse import quote_plus

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
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
    WelcomeSetting,
)
from shared.schemas import (
    ClaimRewardResponse,
    CreateReferralLinkRequest,
    CreateReferralLinkResponse,
    DashboardResponse,
    RecordJoinEventRequest,
    UpsertWelcomeSettingsRequest,
    VerifyMembershipRequest,
    VerifyMembershipResponse,
    WelcomeSettingsResponse,
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


def _get_or_create_welcome_settings(db: Session, chat_id: str) -> WelcomeSetting:
    setting = db.scalar(select(WelcomeSetting).where(WelcomeSetting.chat_id == chat_id))
    if setting:
        return setting

    setting = WelcomeSetting(
        chat_id=chat_id,
        message_template=settings.welcome_message_text,
        button_text=settings.welcome_button_text,
        button_url=settings.welcome_button_url,
    )
    db.add(setting)
    db.flush()
    return setting


async def _is_member(bot_token: str, chat_id: str, user_id: int) -> bool:
    bot = _get_bot(bot_token)
    member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
    return member.status in {"member", "administrator", "creator", "restricted"}


@app.get("/", response_class=HTMLResponse)
def app_home() -> str:
    return _render_html_dashboard(
        title="🤖 Bot Control Center",
        subtitle="Manage verifier, reward, and welcome bot experiences.",
        cards=[
            {
                "title": "Verifier Bot",
                "desc": "Guide users through channel/group verification with one click.",
                "action_label": "Open Verifier Dashboard",
                "action_url": "/dashboard/verifier",
            },
            {
                "title": "Reward Bot",
                "desc": "Track verification reward status, referrals, and claim totals.",
                "action_label": "Open Reward Dashboard",
                "action_url": "/dashboard/reward",
            },
            {
                "title": "Welcome Bot",
                "desc": "Customize your group welcome message and CTA button.",
                "action_label": "Open Welcome Dashboard",
                "action_url": f"/dashboard/welcome?chat_id={quote_plus(settings.target_group_id)}",
            },
        ],
    )


@app.get("/dashboard/verifier", response_class=HTMLResponse)
def verifier_dashboard_page() -> str:
    return _render_html_dashboard(
        title="✅ Verifier Bot Dashboard",
        subtitle="Share these links with users so they can complete verification quickly.",
        cards=[
            {
                "title": "Join Channel Link",
                "desc": settings.channel_join_url,
                "action_label": "Open Channel",
                "action_url": settings.channel_join_url,
            },
            {
                "title": "Join Group Link",
                "desc": settings.group_join_url,
                "action_label": "Open Group",
                "action_url": settings.group_join_url,
            },
        ],
    )


@app.get("/dashboard/reward", response_class=HTMLResponse)
def reward_dashboard_page() -> str:
    return _render_html_dashboard(
        title="🎁 Reward Bot Dashboard",
        subtitle="Users can check status and claim rewards directly from Telegram.",
        cards=[
            {
                "title": "Verification Reward",
                "desc": f"Current amount: {settings.verification_reward_amount}",
                "action_label": "Open API Dashboard Endpoint",
                "action_url": "/docs#/default/get_dashboard_dashboard__telegram_user_id__get",
            },
            {
                "title": "Referral Reward",
                "desc": f"Current amount: {settings.referral_reward_amount}",
                "action_label": "Open Claim Endpoint",
                "action_url": "/docs#/default/claim_reward_status_rewards__telegram_user_id__claim_post",
            },
        ],
    )


@app.get("/dashboard/welcome", response_class=HTMLResponse)
def welcome_dashboard_page(chat_id: str) -> str:
    escaped_chat_id = html.escape(chat_id)
    return f"""
    <!doctype html>
    <html>
      <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>Welcome Bot Dashboard</title>
        <style>
          body {{ font-family: Inter, system-ui, sans-serif; background: #0f172a; color: #e2e8f0; padding: 24px; }}
          .card {{ max-width: 760px; margin: 0 auto; background: #111827; border: 1px solid #334155; border-radius: 16px; padding: 20px; }}
          input, textarea {{ width: 100%; padding: 10px; border-radius: 10px; border: 1px solid #475569; background: #0b1220; color: #e2e8f0; margin-top: 8px; margin-bottom: 14px; }}
          button {{ background: linear-gradient(90deg, #14b8a6, #6366f1); color: white; border: none; border-radius: 10px; padding: 10px 16px; cursor: pointer; font-weight: 600; }}
          .hint {{ color: #94a3b8; font-size: 13px; }}
        </style>
      </head>
      <body>
        <div class=\"card\">
          <h1>👋 Welcome Bot Dashboard</h1>
          <p class=\"hint\">Customize the welcome experience for chat_id: <code>{escaped_chat_id}</code></p>
          <form id=\"welcome-form\">
            <label>Message Template</label>
            <textarea id=\"message_template\" rows=\"5\"></textarea>
            <p class=\"hint\">Available placeholders: {'{'}first_name{'}'}, {'{'}username{'}'}, {'{'}chat_title{'}'}.</p>
            <label>Button Text</label>
            <input id=\"button_text\" type=\"text\" />
            <label>Button URL</label>
            <input id=\"button_url\" type=\"url\" />
            <button type=\"submit\">Save Welcome Settings</button>
          </form>
          <p id=\"status\" class=\"hint\"></p>
        </div>
        <script>
          const chatId = {chat_id!r};
          async function load() {{
            const res = await fetch(`/welcome-settings/${{encodeURIComponent(chatId)}}`);
            const data = await res.json();
            document.getElementById('message_template').value = data.message_template || '';
            document.getElementById('button_text').value = data.button_text || '';
            document.getElementById('button_url').value = data.button_url || '';
          }}
          document.getElementById('welcome-form').addEventListener('submit', async (e) => {{
            e.preventDefault();
            const payload = {{
              chat_id: chatId,
              message_template: document.getElementById('message_template').value,
              button_text: document.getElementById('button_text').value || null,
              button_url: document.getElementById('button_url').value || null,
            }};
            const res = await fetch('/welcome-settings', {{
              method: 'POST',
              headers: {{'Content-Type': 'application/json'}},
              body: JSON.stringify(payload),
            }});
            document.getElementById('status').textContent = res.ok ? 'Saved successfully ✅' : 'Save failed ❌';
          }});
          load();
        </script>
      </body>
    </html>
    """


def _render_html_dashboard(title: str, subtitle: str, cards: list[dict[str, str]]) -> str:
    card_html = "\n".join(
        f"""
        <div class=\"card\">
          <h2>{html.escape(card['title'])}</h2>
          <p>{html.escape(card['desc'])}</p>
          <a href=\"{html.escape(card['action_url'])}\">{html.escape(card['action_label'])}</a>
        </div>
        """
        for card in cards
    )
    return f"""
    <!doctype html>
    <html>
      <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>{html.escape(title)}</title>
        <style>
          body {{ font-family: Inter, system-ui, sans-serif; background: #020617; color: #e2e8f0; margin: 0; padding: 28px; }}
          .wrap {{ max-width: 980px; margin: 0 auto; }}
          h1 {{ margin-bottom: 8px; }}
          .sub {{ color: #94a3b8; margin-bottom: 20px; }}
          .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
          .card {{ background: linear-gradient(140deg, #0f172a, #1e293b); border-radius: 16px; border: 1px solid #334155; padding: 18px; }}
          .card a {{ display: inline-block; margin-top: 12px; text-decoration: none; color: white; background: linear-gradient(90deg, #14b8a6, #4f46e5); border-radius: 10px; padding: 10px 14px; font-weight: 600; }}
        </style>
      </head>
      <body>
        <div class=\"wrap\">
          <h1>{html.escape(title)}</h1>
          <p class=\"sub\">{html.escape(subtitle)}</p>
          <div class=\"grid\">{card_html}</div>
        </div>
      </body>
    </html>
    """


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


@app.get("/welcome-settings/{chat_id}", response_model=WelcomeSettingsResponse)
def get_welcome_settings(chat_id: str, db: Session = Depends(get_db)) -> WelcomeSettingsResponse:
    setting = _get_or_create_welcome_settings(db, chat_id)
    db.commit()
    return WelcomeSettingsResponse(
        chat_id=setting.chat_id,
        message_template=setting.message_template,
        button_text=setting.button_text,
        button_url=setting.button_url,
    )


@app.post("/welcome-settings", response_model=WelcomeSettingsResponse)
def upsert_welcome_settings(payload: UpsertWelcomeSettingsRequest, db: Session = Depends(get_db)) -> WelcomeSettingsResponse:
    setting = _get_or_create_welcome_settings(db, payload.chat_id)
    setting.message_template = payload.message_template
    setting.button_text = payload.button_text
    setting.button_url = payload.button_url
    db.commit()
    db.refresh(setting)
    return WelcomeSettingsResponse(
        chat_id=setting.chat_id,
        message_template=setting.message_template,
        button_text=setting.button_text,
        button_url=setting.button_url,
    )
