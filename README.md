# SureHub

Personal modular platform to manage finances, music, and daily life — powered by AI.

Self-hosted, single-user, no cloud dependency. Runs locally and deploys to a homelab server.

## Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI + SQLModel |
| Database | SQLite (local and prod) |
| Frontend | React + Vite (CSS custom properties, no UI framework) |
| AI | Claude API (Anthropic) |
| Bot | Telegram (python-telegram-bot) |
| Infra | Docker compose on homelab server `surehub-home` (auto-deploy on merge) |

## Modules

| Module | Status | Description |
|---|---|---|
| Finance | ✅ | Expense tracking, categories, recurring costs, monthly summary, ING import |
| Spotify | ✅ | Library analysis via Claude, OAuth via Telegram |
| Inbox | ✅ | Obsidian note capture → AI classification → tasks/notes/calendar events |
| News | 🗓️ planned | Briefings and topic aggregation |
| Email | 🗓️ planned | Gmail summaries and automation |

## Getting Started

### Requirements
- Python 3.12+
- Node.js 18+
- A `.env` file (see `.env.example`)

### Run locally

```bash
# venv lives in .venv
source .venv/bin/activate

# Backend (from repo root, venv active)
uvicorn app.main:app --reload --port 8001

# Telegram bot (separate terminal)
python -m bot.run

# Frontend (separate terminal)
cd frontend && npm run dev
```

Or use `dev.bat` (Windows) to launch all three at once.

> Note: prod (homelab `surehub-home`) holds the canonical SQLite DB. Don't run the bot
> locally with the prod token (polling conflict). See `CLAUDE.md` for operating against prod.

### Ports
- Backend: `8001`
- Frontend: `5174`

## License

Personal use. Not intended for public deployment.
