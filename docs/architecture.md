# Architecture & Development Reference

Internal reference for decisions, conventions, and structure. For current module state and bot commands, **`CLAUDE.md` is the source of truth**.

## Project Structure

```
app/
  modules/<module>/
    models.py     # SQLModel table models
    service.py    # business logic, receives Session
    parser.py     # input parsing (if applicable)
  services/
    llm.py        # LLM entrypoints (chat/complete_tags/complete_event) + call logging
    llm_router.py # LiteLLM tier→model routing (cloud=Sonnet, local_ok=Haiku) + fallback
    calendar.py   # Google Calendar API (CALENDAR_COLORS, all-day, create_event); creds via modules/calendar
  modules/
    calendar/     # OAuth web flow + token in SQLite (GoogleToken); get_credentials for services/calendar.py
    llm_log/      # LLMCall model — every LLM call logged to SQLite (llm_calls)
  routers/
    finanzas.py   # REST endpoints per module
  config.py       # Settings from .env
  database.py     # engine, get_session, create_db
  models.py       # imports all models (for create_db)
  main.py         # FastAPI app
bot/
  handlers.py         # Telegram handlers (capture, finance, analisis)
  inbox_handlers.py   # /inbox digest + callbacks + daily job
  help_text.py        # /help + Telegram command menu (bot_commands)
  run.py              # bot entrypoint (calls create_db on start)
frontend/         # React + Vite, proxy /api → localhost:8001
scripts/          # one-off migration and seed scripts
docs/             # architecture and specs
```

## Architecture Decisions

**SQLite in local and prod** — canonical DB on homelab volume `/srv/surehub/data/surehub.db`. `DATABASE_URL` only.

**Telegram polling everywhere** — webhook mode was never implemented. Bot and FastAPI run as separate processes locally, separate containers in prod. Never run the bot locally with the prod token (polling conflict).

**No conversation history in bot** — each message is independent. Text/voice either parses as expense/note or gets "No entiendo". No free-form chat.

**Bot is capture-first** — Telegram command menu is minimal (`help`, `mes`, `gastos`, `inbox`). Notes and expenses work without commands.

**Memory module** — SQLite + frontend UI only. Injected into `/analisis` if facts exist. No `/recuerda` in Telegram.

**`/analisis` requires confirmation** — inline buttons before Claude Sonnet runs (cost control). Not in Telegram menu.

**Obsidian vault** — `OBSIDIAN_VAULT_PATH`. Bot writes `inbox/*.md`; inbox module moves to `archivo/` or `_descartado/`. Moving the vault requires updating env + Docker mount on server.

**Claude models** — Sonnet (`LLM_MODEL`) for `/analisis` and inbox event date extraction (`extract_event`); Haiku (`TAG_MODEL`) for note tags and inbox classification. All calls go through `services/llm_router.py` (LiteLLM, tier→model + fallback) and are logged to the `llm_calls` table (`modules/llm_log`), never straight to the Anthropic SDK.

**Inbox events → Google Calendar** — notes classified as `event` get a Sonnet date/duration/theme extraction (2nd LLM call, only for events). Approval is per-event in the digest; `create_event` (`services/calendar.py`) inserts into Google Calendar with a theme color. Auth is split: `modules/calendar/` runs the OAuth **web flow** and stores the token in SQLite (`google_tokens`), exposing `get_credentials`; `services/calendar.py` asks it for live credentials. One-time auth: visit `/api/calendar/oauth/init` through an SSH tunnel to `localhost:8001`.

**Single user, no auth** — personal use only.

**Frontend proxy** — Vite proxies `/api` → FastAPI in dev. Same origin in prod.

## Adding a New Module

1. Create `app/modules/<module>/models.py` + `service.py`
2. Register models in `app/models.py` so `create_db()` picks them up
3. Add router in `app/routers/<module>.py`
4. Register router in `app/main.py`
5. Add frontend view in `frontend/src/components/`
6. Add nav entry in `frontend/src/components/Sidebar.jsx`
7. Update `CLAUDE.md` (and this file if the decision is architectural)

## DB Migrations

SQLite supports `ALTER TABLE ADD COLUMN` without data loss. For bigger changes, write a script in `scripts/` and run once.

## Commits, deploy, and docs

- Format: `<type>: <what>` — English, types `feat` | `fix` | `refactor` | `chore`
- On feature close (tests OK, user confirms): commit + push to `main` → CI → auto-deploy to `surehub-home`
- **Update docs in the same commit** when behavior changes: `CLAUDE.md`, `docs/architecture.md`, `.env.example` as applicable

## UI Design System

Dark, minimal, non-saturating palette. Full rules in `frontend/src/styles.js` and enforced via `ui-ecosystem` skill.

Key rules:
- No electric blue — accent is `--accent` (#c8f0dc) only, max one per view
- Lists of 3+ items use flat rows with `border-b`, not individual cards
- Typography in 3 levels: label (`text-xs uppercase tracking-wide`), content (`text-sm`), metadata (`text-xs text-muted`)
- No native date pickers without full style reset

**Mandatory flow for UI changes:** screenshot audit → propose in text → implement → screenshot verify.
