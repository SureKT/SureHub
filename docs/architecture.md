# Architecture & Development Reference

Internal reference for decisions, conventions, and structure.

## Project Structure

```
app/
  modules/<module>/
    models.py     # SQLModel table models
    service.py    # business logic, receives Session
    parser.py     # input parsing (if applicable)
  services/
    llm.py        # Claude API wrapper
  routers/
    finanzas.py   # REST endpoints per module
  config.py       # Settings from .env
  database.py     # engine, get_session, create_db
  models.py       # imports all models (for create_db)
  main.py         # FastAPI app
bot/
  handlers.py         # Telegram handlers
  inbox_handlers.py   # /inbox digest + callbacks + job diario
  help_text.py        # /help y menú de comandos
  run.py              # bot entrypoint (calls create_db on start)
frontend/         # React + Vite, proxy /api → localhost:8001
scripts/          # one-off migration and seed scripts
docs/             # architecture and specs
```

## Architecture Decisions

**SQLite in dev, PostgreSQL in prod** — swap via `DATABASE_URL` only. No code changes needed.

**Telegram polling in dev, webhook in prod** — swap via `TELEGRAM_MODE`. Bot and FastAPI run as separate processes locally, same container in prod.

**No conversation history in bot** — each message is independent. Deliberate choice; add only if real usage justifies it.

**Manual memory via `/recuerda`** — injected into Claude system prompt. Simple, controllable.

**Claude model: `claude-sonnet-4-6`** — change only with explicit reason.

**Single user, no auth** — SureHub is personal. No multi-user support planned.

**Frontend proxy** — Vite proxies `/api` → FastAPI in dev. Same origin in prod.

## Adding a New Module

1. Create `app/modules/<module>/models.py` + `service.py`
2. Register models in `app/models.py` so `create_db()` picks them up
3. Add router in `app/routers/<module>.py`
4. Register router in `app/main.py`
5. Add frontend view in `frontend/src/components/`
6. Add nav entry in `frontend/src/components/Sidebar.jsx`

## DB Migrations

SQLite supports `ALTER TABLE ADD COLUMN` without data loss. For bigger changes, write a script in `scripts/` and run once.

## Commits

Format: `<type>: <what>` with body if needed.
Types: `feat`, `fix`, `refactor`, `chore`
Language: English.

Auto-commit when user confirms something works ("funciona", "listo", "perfecto", "ok") and changes are substantial enough.

## UI Design System

Dark, minimal, non-saturating palette. Full rules in `frontend/src/styles.js` and enforced via `ui-ecosystem` skill.

Key rules:
- No electric blue — accent is `--accent` (#c8f0dc) only, max one per view
- Lists of 3+ items use flat rows with `border-b`, not individual cards
- Typography in 3 levels: label (`text-xs uppercase tracking-wide`), content (`text-sm`), metadata (`text-xs text-muted`)
- No native date pickers without full style reset

**Mandatory flow for UI changes:** screenshot audit → propose in text → implement → screenshot verify.

## Vision (Long-term)

- Dual sidebar: left for module nav, right for module config/explore
- Pastel aesthetic variant
- Login + API credentials management
- Production: Hetzner VPS, Docker, Telegram webhook, PostgreSQL
