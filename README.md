# Telegram Crypto Reward System (Production-Minded Starter)

This project provides a **Telegram-native UX** (no external frontend required):

- **Verifier Bot**: in-chat verification dashboard with progress + actions
- **Reward Bot**: in-chat rewards dashboard with working callback buttons
- **Welcome Bot**: in-chat control panel + configurable onboarding messages
- **FastAPI Backend**: API service for verification, rewards, referrals, and welcome settings

## Architecture

```text
verifier_bot/   -> in-chat verification panel + membership verification actions
reward_bot/     -> in-chat reward dashboard + referral tracking
welcome_bot/    -> in-chat settings panel + new-member welcome messages
backend/        -> API endpoints (verification, rewards, referrals, welcome settings)
shared/         -> config, DB session, models, schemas, logging, Telegram UI helpers
```

## Reward flow (simple explanation)

1. **Verification reward**
   - User joins required channel + group.
   - Verifier Bot calls backend verification.
   - If both checks pass, backend marks user verified and creates verification reward.

2. **Referral reward**
   - Verified user has a personal invite link.
   - New user joins group through that link (`/referral-events/record`).
   - Inviter reward is granted **only when invited user later completes verification**.
   - Duplicate and self-referrals are prevented.

## Pending / approved / rejected statuses

- `pending`: reward created but not yet finalized.
- `approved`: reward finalized as earned.
- `rejected`: reward denied (for example fraud-flag path).

If you do not need manual review, you can auto-approve in your claim/admin flow and keep user-facing wording simple.

## Reward Bot UX

`/start` shows:
- Verification status (Verified / Not Verified)
- Verification reward status
- Referral reward status
- Total referrals
- Personal invite link

Buttons (all working):
- Refresh
- My Rewards
- My Referral Link
- How It Works
- Back (in sub-pages)

## API endpoints

- `POST /verify-membership`
- `POST /referral-links/create`
- `POST /referral-events/record`
- `GET /dashboard/{telegram_user_id}`
- `POST /rewards/{telegram_user_id}/claim`
- `GET /welcome-settings/{chat_id}`
- `POST /welcome-settings`

## Setup

1. Copy env template:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` with your real Telegram tokens/IDs.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run backend:
   ```bash
   uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
   ```
5. Run bots:
   ```bash
   python -m verifier_bot.bot
   python -m reward_bot.bot
   python -m welcome_bot.bot
   ```

## UI customization

All panel text and button labels are configurable from `.env` (for example: `VERIFIER_BTN_*`, `REWARD_BTN_*`, `WELCOME_BTN_*`).

## Quick API example: update welcome settings

```bash
curl -X POST http://127.0.0.1:8000/welcome-settings \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": "-1009876543210",
    "message_template": "👋 Welcome {first_name} to {chat_title}! Please read the rules.",
    "button_text": "📌 Rules",
    "button_url": "https://t.me/your_group/1"
  }'
```

## Telegram admin permissions checklist

### Verifier Bot
- Added to both target channel and group
- Can read member status

### Reward Bot
- Admin in target group
- Can create invite links
- Can receive join updates

### Welcome Bot
- Added to target group
- Can send welcome messages
- Can receive member join updates
