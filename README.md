# SureHub

Personal modular platform to manage finances, calendar, and daily life — powered by AI.

## What is SureHub?

SureHub is a self-hosted personal dashboard built for a single user. It centralizes daily tools — expense tracking, calendar management, and more — with an AI layer accessible via Telegram bot.

No cloud dependency. No subscriptions. Runs on a local machine and deploys to a small VPS.

## Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI + SQLModel |
| Database | SQLite (local) / PostgreSQL (prod) |
| Frontend | React + Vite + Tailwind |
| AI | Claude API (Anthropic) |
| Bot | Telegram (python-telegram-bot) |
| Infra | Docker + Hetzner VPS (~€4/mo) |

## Modules

### ✅ Finanzas
Track expenses and recurring costs.
- Monthly summary with budget vs actual
- Expense log with category inference
- Category management (variable / fixed)
- Recurring expenses tracker
- Import from CSV (Coda)

### 🚧 Calendario *(in progress)*
Manage Google Calendar via natural language through Telegram.
- Create and reschedule events by chatting
- Color and reminder configuration per event type

### 🗓️ Planned

| Module | Description |
|---|---|
| Diario | Daily journal with records, tasks, and timeline |
| Correo | Email summaries, rules, and document analysis |
| Noticias | Briefings and context aggregation |

## Getting Started

### Requirements
- Python 3.11+
- Node.js 18+
- A `.env` file (see `.env.example`)

### Run locally

```bash
# Backend
uvicorn app.main:app --reload

# Telegram bot (separate terminal)
python -m bot.run

# Frontend (separate terminal)
cd frontend && npm run dev
```

Or use the included `dev.bat` (Windows) to launch all three at once.

### Ports
- Backend: `8001`
- Frontend: `5174`

## Roadmap

- [ ] Google Calendar module
- [ ] Diario module
- [ ] Email integration
- [ ] Right sidebar for module config
- [ ] Production deploy (Docker + Hetzner)

## License

Personal use. Not intended for public deployment.
