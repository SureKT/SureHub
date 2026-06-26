# SureHub

> A self-hosted, LLM-powered personal hub — finances, note capture, and calendar
> automation — driven from a Telegram chat. Single-user, self-hosted, runs 24/7
> on my own homelab.

SureHub is the **capture + orchestration layer** of a self-hosted homelab. The
goal is frictionless input and AI-driven structuring: you message a Telegram bot
in plain language, and an LLM turns it into categorized expenses, tagged notes,
or calendar events — no forms, no manual filing. Your data lives in your own
database and Obsidian vault, not in a SaaS product; the only external calls are
the LLM API and Google Calendar, by choice.

## Why

Most personal-finance and note apps each solve one slice and hold your data in
their cloud. SureHub inverts that: one self-hosted backend where **capture is a
chat message** and the LLM does the structuring. It deliberately does *not*
reinvent what's already solved — notes live in an Obsidian vault, search is
delegated elsewhere — SureHub focuses on capture and routing.

## What it does

- **Finance** — Log an expense by texting `lunch 12` (or `12 lunch`); keyword
  rules or inline buttons assign the category. Monthly summaries with
  fixed-vs-variable split, budget alerts, recurring costs, and bank-CSV import.
- **Inbox** — Free-text or voice notes land as Markdown in an Obsidian vault.
  An LLM classifies each as `task` / `note` / `event`; a daily Telegram digest
  proposes actions you approve in batch. Events get date/duration extracted and
  pushed to Google Calendar.

## Architecture

```
Telegram bot ─┐
              ├─► FastAPI + SQLModel ─► SQLite (canonical, on the server)
Frontend ─────┘            │
                           ├─► Claude API (Sonnet / Haiku, per task)
                           └─► Obsidian vault (Markdown, synced via Syncthing)
```

| Layer | Tech |
|---|---|
| Backend | FastAPI + SQLModel |
| Database | SQLite (local and prod) |
| Frontend | React + Vite (CSS custom properties, no UI framework) |
| AI | Claude API — Sonnet + Haiku |
| Bot | Telegram (python-telegram-bot) |
| Infra | Docker Compose on homelab `surehub-home`, auto-deploy on merge |

## Engineering decisions (the *why*)

- **Multi-model LLM, chosen per task.** Claude **Sonnet** handles
  reasoning-heavy monthly financial analysis; **Haiku** does cheap, fast note
  classification and tag extraction. Matching model to job keeps latency and
  cost low (~$5–15/month) without dumbing down the hard calls. LLM failure
  always degrades gracefully — a note never gets lost, it falls back to
  `uncertain` for manual review.
- **Capture without commands.** The bot's primary UX is *not* slash commands —
  you just type or send a voice note. The `/` menu is intentionally minimal (4
  entries). Lowering capture friction is the whole point; commands are the
  fallback, not the interface.
- **Obsidian as the source of truth for notes.** The bot writes Markdown into a
  vault synced by Syncthing across devices. Every Inbox action is **reversible
  because it's just a file move** (`archivo/`, `_descartado/`, a line in
  `Tareas.md`) — no destructive state, easy to audit.
- **SQLite in local *and* prod.** Single user, personal scale — Postgres would
  be ceremony with no payoff. The canonical DB lives on the server; local dev
  runs against its own copy.
- **Separate bot and API processes.** The Telegram bot (polling locally, webhook
  in prod) and the FastAPI app run as independent processes / containers, so one
  can restart without taking the other down.
- **Self-hosted with CI/CD.** Push to `main` → GitHub Actions CI → automatic
  deploy to the homelab via Docker Compose if CI passes.

### A bug worth keeping

The DB ended up with **three date formats** — CSV import with microseconds,
naive imports without them, and tz-aware timestamps from the bot. Comparing
month ranges against `datetime` bounds silently **dropped expenses logged at
midnight on day 1**. Fix: compare against *string* bounds instead of tz-aware
datetimes, so all three formats sort correctly. A reminder that "just store a
date" is rarely just that.

## Getting Started

**Requirements:** Python 3.12+, Node.js 18+, a `.env` (see `.env.example`).

```bash
source .venv/bin/activate          # venv lives in .venv

uvicorn app.main:app --reload --port 8001   # backend
python -m bot.run                            # bot (separate terminal)
cd frontend && npm run dev                   # frontend (separate terminal)
```

Ports: backend `8001`, frontend `5174`.

> Prod (homelab `surehub-home`) holds the canonical SQLite DB. Don't run the bot
> locally with the prod token — polling conflict. See `CLAUDE.md` for operating
> against prod.

## License

Personal project. Shared as a portfolio reference, not intended for public
deployment.
