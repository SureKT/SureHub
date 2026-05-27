# SureHub

Personal modular platform to manage finances, music, journaling, and daily life — powered by AI.

Self-hosted, single-user, no cloud dependency. Runs locally and deploys to a small VPS.

## Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI + SQLModel |
| Database | SQLite (local) / PostgreSQL (prod) |
| Frontend | React + Vite (CSS custom properties, no UI framework) |
| AI | Claude API (Anthropic) |
| Bot | Telegram (python-telegram-bot) |
| Infra | Docker + Hetzner VPS (~€4/mo) — planned |

## Modules

| Module | Status | Description |
|---|---|---|
| Finance | ✅ | Expense tracking, categories, recurring costs, monthly summary, ING import |
| Diary | ✅ | Journal entries with text + structured metrics, timeline view |
| Spotify | ✅ | Library analysis via Claude, OAuth via Telegram |
| Calendar | 🗓️ planned | Google Calendar management via natural language |
| News | 🗓️ planned | Briefings and topic aggregation |
| Email | 🗓️ planned | Gmail summaries and automation |

## Getting Started

### Requirements
- Python 3.11+
- Node.js 18+
- A `.env` file (see `.env.example`)

### Run locally

```bash
# Backend (from repo root, venv active)
uvicorn app.main:app --reload --port 8001

# Telegram bot (separate terminal)
python -m bot.run

# Frontend (separate terminal)
cd frontend && npm run dev
```

Or use `dev.bat` (Windows) to launch all three at once.

### Ports
- Backend: `8001`
- Frontend: `5174`

## License

Personal use. Not intended for public deployment.
