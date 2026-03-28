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