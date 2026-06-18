# SureHub

Plataforma personal modular: finanzas, noticias, automatizaciones, agente IA.
Usuario único: Sure (uso doméstico, sin auth, sin multiusuario).
Stack: FastAPI + SQLModel + SQLite + Telegram bot + Claude API.

> **Contexto de infra:** SureHub es la pieza custom de un proyecto mayor (homelab self-hosted, Bloque A). El estado de la infra y el server viven en el repo `SureKT/homelab` (`CLAUDE.md` + `STATE.md`). Para trabajo de infra/servidor, ese repo es la fuente de verdad. Convención: pull al empezar, actualiza estado y push al cambiar algo.

> **Roadmap ("no reinventar la rueda"):** SureHub = **capa de captura+orquestación**, no reimplementa lo ya resuelto. Core propio: bot Telegram, memoria del bot, finanzas mínimo. NO construir: Diario (→ Obsidian, módulo retirado), Notas (→ vault Obsidian, solo handler bot), índice/búsqueda IA (→ Khoj). Finanzas: si piden presupuestos/reglas/multi-cuenta → Firefly III. Detalle/estado en `SureKT/homelab` → `STATE.md`.

## Comandos
- Backend: `uvicorn app.main:app --reload` (desde raíz, venv activado)
- Bot: `python -m bot.run` (segunda terminal, venv activado)
- Frontend: `cd frontend && npm run dev` (tercera terminal)
- Scripts puntuales: `python scripts/<script>.py` (desde raíz, venv activado)

## Estructura
```
app/
  modules/<modulo>/
    models.py    # SQLModel table models
    service.py   # lógica de negocio, recibe Session
    parser.py    # parsing de input (si aplica)
  services/
    llm.py       # wrapper Claude API
  routers/
    finanzas.py  # endpoints REST del módulo finanzas
  config.py      # Settings desde .env
  database.py    # engine, get_session, create_db
  models.py      # importa todos los modelos (para create_db)
  main.py        # FastAPI app
bot/
  handlers.py    # handlers de Telegram
  inbox_handlers.py  # /inbox, digest, callbacks, job diario
  help_text.py   # /help y menú de comandos
  run.py         # arranque del bot (llama a create_db al inicio)
frontend/        # React + Vite, proxy /api → localhost:8001
scripts/         # scripts de migración y seed (uso puntual, no producción)
```

## Convenciones
- Código en inglés: modelos, servicios, routers, frontend, API keys, labels UI
- Bot Telegram: respuestas en español (Sure habla español con el bot)
- Nuevos módulos siempre en `app/modules/<module>/` con models + service
- Registrar modelo nuevo en `app/models.py` para que create_db() lo cree
- `get_session()` con `next()` en handlers — no usar como context manager en sync code
- Variables de entorno: siempre en `.env`, nunca hardcodeadas, documentar en `.env.example`
- Sin comentarios obvios — solo si el WHY no es evidente
- Migraciones de DB: SQLite soporta ALTER TABLE ADD COLUMN sin perder datos. Para cambios mayores, script en `scripts/`

## Commits
- Ejecutar commit automáticamente (sin pedir permiso) cuando:
  - El usuario confirma que algo funciona ("funciona", "listo", "perfecto", "ok")
  - Y hay cambios suficientes (feature completa, fix real, módulo nuevo)
- NO commitear por cambios triviales (un typo, un print de debug, ajuste de texto)
- Mensajes en inglés, formato: `<tipo>: <qué> + detalle en body si aplica`
- Tipos: `feat`, `fix`, `refactor`, `chore`

## Decisiones de arquitectura
- **SQLite en local y prod** — prod corre en el server homelab (`surehub-home`), DB canónica en `/srv/surehub/data/surehub.db`. `DATABASE_URL` apunta ahí; Postgres descartado por ahora (uso personal, SQLite sobra)
- **DB canónica = server**. El PC ya no corre SureHub (no arrancar `bot.run` en local con el mismo token → conflicto polling)
- Telegram polling en local, webhook en prod — cambio en TELEGRAM_MODE
- Bot y FastAPI corren como procesos separados en local, containers separados en prod (api/bot/frontend vía docker compose en el server)
- Claude API model: `claude-sonnet-4-6` — cambiar solo si hay razón explícita
- No hay historial de conversación en el bot — cada mensaje es independiente (decisión consciente, añadir si el uso real lo justifica)
- Memoria del bot: manual vía /recuerda. Se inyecta en system prompt de Claude
- Frontend consume API en /api (proxy Vite → FastAPI). En prod, mismo origen

## Estado actual del módulo Inbox (Obsidian)

- Módulo `app/modules/inbox/` + handlers en `bot/inbox_handlers.py`
- Modelo `InboxItem` en SQLite (`inbox_items`): trackea cada `.md` visto en `inbox/` + propuesta IA + estado
- Clasificación Haiku vía `complete_tags` → `task` | `note` | `uncertain` (fallo LLM → `uncertain`, nunca se pierde la nota)
- Comando `/inbox`: escanea notas nuevas, envía digest Telegram con aprobación en lote
- Digest diario: `JobQueue.run_daily` a las `INBOX_DIGEST_HOUR` (default 9, `TIMEZONE`)
- Acciones reversibles (mover `.md`): `task` → línea en `Tareas.md` + `archivo/`; `note` → `archivo/`; `discard` → `inbox/_descartado/`
- Notas `uncertain` (o voz 🎤): botones individuales + flujo editar (siguiente mensaje de texto)
- Spec: `docs/superpowers/specs/2026-06-18-inbox-auto-processing-design.md`
- Fase 2 pendiente: eventos → Google Calendar (OAuth)

## Estado actual del módulo Finanzas
- Modelos: `Category` (name, type, monthly_estimate, active) + `Expense` (category_id FK, amount, description, date, source) + `RecurringExpense` (name, amount, category_id, day, active)
- `Category.active`: soft delete — categorías inactivas ocultas en UI pero los gastos históricos mantienen el FK
- Coste fijo = módulo recurrente (single source). Anuales (Google One, Amazon Prime) **prorrateados** = anual/12. Filas fijas enlazadas vía `recurring_id` para que `generate_recurring` no las duplique
- ⚠️ Subs anuales prorrateadas: **no anotar el cargo anual real** cuando caiga en el banco — el recurrente mensual ya lo cubre; anotarlo duplica
- Reembolsos (bizum recibido) se registran como ajuste negativo en `Varios` (decisión: no construir split-tracking; si crece → Firefly III)
- **Fechas en formato mixto** en la DB: csv con microsegundos (`...00:00:00.000000`), import sin ellos (`...00:00:00`), bot tz-aware (`...+00:00`). `_month_range` devuelve **bounds string** (no `datetime`) para comparar bien con los tres — con bound `datetime` se caían los gastos del día 1 a medianoche (ver `service.py`). No volver a tz-aware ahí
- Telegram parser detects "description amount" or "amount description" pattern, infers category by keywords
- Import source values: `telegram`, `manual`, `import`, `recurring`, `csv` (Coda)
- API prefix: `/api/finance` (categories, expenses, summary, evolution, months, import)
- Ports: backend 8001, frontend 5174

## Infraestructura
- **Prod (actual):** server homelab `surehub-home` (Ubuntu, Tailscale). Docker compose: api (FastAPI interno) + bot (polling) + frontend (nginx `:8001`, proxya `/api`). DB SQLite canónica en volumen `/srv/surehub/data`. Auto-deploy on merge a main (`.github/workflows/deploy.yml`, gated por `ci`). Detalle en repo `SureKT/homelab` → `docs/surehub.md`
- Local dev: PC + 3 terminales (backend, bot, frontend) contra SQLite local — pero la verdad vive en el server
- Claude API: ~$5-15/mes uso personal moderado
