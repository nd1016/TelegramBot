# Telegram Crypto Reward System (Production-Minded Starter)

This project now includes **3 bots + web dashboards**:

- **Verifier Bot** (membership checks)
- **Reward Bot** (rewards + referrals)
- **Welcome Bot** (greets new group members)
- **FastAPI backend** with **fancy dashboard pages** for all of them

## Architecture

```text
verifier_bot/   -> verifies group/channel membership
reward_bot/     -> user reward dashboard, claim command, join-event tracking
welcome_bot/    -> sends customizable welcome message for new group members
backend/        -> API + dashboard pages + welcome settings
shared/         -> config, DB session, models, schemas, logging
```

## New in this update

### 1) Welcome Bot
- Listens for `NEW_CHAT_MEMBERS` in your target group.
- Pulls welcome settings from backend:
  - `message_template`
  - optional button text + URL
- Supports placeholders in welcome template:
  - `{first_name}`
  - `{username}`
  - `{chat_title}`

### 2) Fancy Dashboards
Backend serves responsive UI pages:
- `/` → control center
- `/dashboard/verifier`
- `/dashboard/reward`
- `/dashboard/welcome?chat_id=<your_group_id>`

### 3) Welcome Settings API
- `GET /welcome-settings/{chat_id}`
- `POST /welcome-settings`

Welcome settings are stored in DB table `welcome_settings`.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set environment variables (example):
   ```bash
   export DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/rewards_db"
   export BACKEND_HOST="127.0.0.1"
   export BACKEND_PORT="8000"

   export VERIFIER_BOT_TOKEN="<verifier_bot_token>"
   export REWARD_BOT_TOKEN="<reward_bot_token>"
   export WELCOME_BOT_TOKEN="<welcome_bot_token>"

   export TARGET_CHANNEL_ID="-1001234567890"
   export TARGET_GROUP_ID="-1009876543210"
   export CHANNEL_JOIN_URL="https://t.me/your_channel"
   export GROUP_JOIN_URL="https://t.me/your_group"

   export WEB_DASHBOARD_BASE_URL="http://127.0.0.1:8000"

   export WELCOME_MESSAGE_TEXT="👋 Welcome {first_name} to {chat_title}!"
   export WELCOME_BUTTON_TEXT="📌 Rules"
   export WELCOME_BUTTON_URL="https://t.me/your_group/1"
   ```

3. Run backend:
   ```bash
   uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
   ```

4. Run bots:
   ```bash
   python -m verifier_bot.bot
   python -m reward_bot.bot
   python -m welcome_bot.bot
   ```

## Copy/Paste snippets

### A) Start Welcome Bot command
```bash
python -m welcome_bot.bot
```

### B) Open Welcome Dashboard
```text
http://127.0.0.1:8000/dashboard/welcome?chat_id=-1009876543210
```

### C) Example welcome settings request
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

## Telegram permissions checklist

### Verifier Bot
- Added to both target channel and group
- Can read membership status

### Reward Bot
- Admin in target group
- Can create invite links
- Can receive join updates

### Welcome Bot
- Added to target group
- Can receive member join updates
- (Optional) send messages with inline buttons

## Notes
- `Base.metadata.create_all()` will create new `welcome_settings` table automatically.
- For production, add migrations (Alembic) and secure admin/dashboard access.
