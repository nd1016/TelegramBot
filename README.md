# 🌟 AutoGPT: the heart of the open-source agent ecosystem
# Telegram Crypto Reward System (Production-Minded Starter)

This project provides a clean, modular starter architecture for a crypto reward campaign using:

- **Verifier Bot** (python-telegram-bot)
- **Reward Bot** (python-telegram-bot)
- **Shared FastAPI backend**
- **PostgreSQL + SQLAlchemy**
- **Environment configuration via python-dotenv**

## Architecture

```text
verifier_bot/   -> verifies group/channel membership
reward_bot/     -> user dashboard, claim command, join-event tracking
backend/        -> API + reward/referral business logic
shared/         -> config, DB session, models, schemas, logging
```

## Project Structure

```text
.
├── verifier_bot/
│   ├── __init__.py
│   ├── api_client.py
│   └── bot.py
├── reward_bot/
│   ├── __init__.py
│   ├── api_client.py
│   └── bot.py
├── backend/
│   ├── __init__.py
│   └── app.py
├── shared/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── logging_utils.py
│   ├── models.py
│   └── schemas.py
├── requirements.txt
├── .env.example
└── README.md
```

## Main Features

### 1) Verifier Bot
- `/start` shows buttons:
  - Join Channel
  - Join Group
  - Verify
- On **Verify** button tap, backend checks membership in both channel and group.
- If user is in both: marked verified.
- If missing one/both: returns friendly missing-items message.

### 2) Reward Bot
- `/start` checks backend dashboard.
- If user is verified:
  - shows reward status
  - referral count
  - personal invite link (creates one if missing)
- If user is not verified: asks user to finish verification first.
- `/claim` triggers reward claim-status handling.

### 3) Referral Tracking
- Verified users get unique invite links.
- Join events from invite links are recorded.
- Inviter gets referral reward only when invited user later becomes verified.
- Duplicate rewards are prevented with DB constraints and checks.

### 4) Anti-abuse rules in this starter
- One verification reward per user (enforced by app logic + uniqueness behavior).
- One referral reward per invited user.
- Self-referrals are rejected.
- Reward statuses supported: `pending`, `approved`, `rejected`.
- Placeholder `fraud_flag` exists on user profile.

### 5) Backend API Endpoints
- `POST /verify-membership`
- `POST /referral-links/create`
- `POST /referral-events/record`
- `GET /dashboard/{telegram_user_id}`
- `POST /rewards/{telegram_user_id}/claim`

### 6) Database Tables
- `users`
- `verifications`
- `referral_links`
- `referral_events`
- `rewards`

## Setup

1. Copy env:
   ```bash
   cp .env.example .env
   ```
2. Install deps:
   ```bash
   pip install -r requirements.txt
   ```
3. Ensure PostgreSQL database exists and `DATABASE_URL` is valid.

## Run Services (long polling)

Run backend:
```bash
uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```

Run verifier bot:
```bash
python -m verifier_bot.bot
```

Run reward bot:
```bash
python -m reward_bot.bot
```

## Telegram Admin Notes (Required Permissions)

### Verifier Bot permissions
- Must be added to both target **channel** and **group**.
- Must have enough rights to read member status (`getChatMember` checks).

### Reward Bot permissions
- Must be admin in the target group with permission to **create invite links**.
- Must receive join updates in the group (privacy mode and bot permissions should allow member updates).

## Production Notes

- Put backend + PostgreSQL behind proper network/security controls.
- Add authentication/authorization for admin-level operations in real deployments.
- Add Alembic migrations for schema evolution.
- Add background jobs/queues for heavy processing.
- Add observability: structured logs, metrics, and alerts.


## Upgrade Note (Telegram IDs)

Telegram user IDs can exceed 32-bit integer range. The `users.telegram_user_id` column uses `BIGINT`.

If you already created tables with `INTEGER`, run:

```sql
ALTER TABLE users ALTER COLUMN telegram_user_id TYPE BIGINT;
```