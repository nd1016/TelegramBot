# Telegram Crypto Reward System (Production-Minded Starter)

This project provides a **Telegram-native UX** (no external frontend required):

- **Verifier Bot**: in-chat verification dashboard with progress + actions
- **Reward Bot**: in-chat rewards dashboard with navigation + claim flow
- **Welcome Bot**: in-chat control panel + configurable onboarding messages
- **FastAPI Backend**: API-only service for business logic and settings

## Architecture

- `verifier_bot/` -> in-chat verification panel + membership verification actions
- `reward_bot/` -> in-chat reward dashboard + referral tracking
- `welcome_bot/` -> in-chat settings panel + new-member welcome messages
- `backend/` -> API endpoints (verification, rewards, referrals, welcome settings)
- `shared/` -> config, DB session, models, schemas, logging, Telegram UI helpers

## Telegram-native dashboard UX

### Reward Bot
- `/start` shows a structured dashboard message inside Telegram.
- Inline button navigation:
  - Refresh
  - My Rewards
  - My Referral Link
  - How It Works
  - Claim Status
- Uses message editing (`edit_message_text`) for smoother navigation and less chat clutter.

### Verifier Bot
- `/start` shows a verification panel in Telegram with current progress:
  - joined channel?
  - joined group?
  - verified?
- Inline buttons:
  - Join Channel
  - Join Group
  - Verify Now
  - Refresh Status
  - Help

### Welcome Bot
- `/start` shows a settings panel in Telegram chat.
- Inline buttons:
  - Refresh Settings
  - Preview Message
  - Help
- New members receive template-based welcome messages from backend settings.

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