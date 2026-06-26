# SureHub

Plataforma personal modular: finanzas, noticias, automatizaciones, agente IA.
Usuario único: Sure (uso doméstico, sin auth, sin multiusuario).
Stack: FastAPI + SQLModel + SQLite + Telegram bot + Claude API.

> **Contexto de infra:** SureHub es la pieza custom de un proyecto mayor (homelab self-hosted, Bloque A). El estado de la infra y el server viven en el repo `SureKT/homelab` (`CLAUDE.md` + `STATE.md`). Para trabajo de infra/servidor, ese repo es la fuente de verdad. Convención: pull al empezar, actualiza estado y push al cambiar algo.

> **Roadmap ("no reinventar la rueda"):** SureHub = **capa de captura+orquestación**, no reimplementa lo ya resuelto. Core propio: bot Telegram, finanzas mínimo. NO construir: Diario (→ Obsidian, módulo retirado), Notas (→ vault Obsidian, captura sin comando), índice/búsqueda IA (→ Khoj). Memoria del bot: solo dashboard web (sin chat conversacional). Finanzas: si piden presupuestos/reglas/multi-cuenta → Firefly III. Detalle/estado en `SureKT/homelab` → `STATE.md`.

## Comandos
- Venv: `source .venv/bin/activate` (carpeta es `.venv`, no `venv`). Binario directo: `.venv/bin/python` (el sistema no tiene `python`, solo `python3`)
- Backend: `uvicorn app.main:app --reload` (desde raíz, venv activado)
- Bot: `python -m bot.run` (segunda terminal, venv activado)
- Frontend: `cd frontend && npm run dev` (tercera terminal)
- Scripts puntuales: `python scripts/<script>.py` (desde raíz, venv activado)

## Operar contra prod (server homelab)
- SSH: `ssh hub` (alias correcto; `ssh surehub-home` falla auth)
- DB canónica: `/srv/surehub/data/surehub.db` en el server — **no editar la DB local**, la verdad vive en prod
- Editar datos desde local sin SSH: API HTTP vía Tailscale `http://surehub-home:8001/api/finance/...`. Verbos: `POST` crear, `PATCH /expenses/{id}` y `PATCH /categories/{id}` editar (NO `PUT`), `DELETE`

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
- **Documentación:** si cambia comportamiento visible (bot, API, módulos, env vars, infra), actualizar `CLAUDE.md` y lo que aplique (`docs/architecture.md`, `.env.example`) en el mismo commit — no cerrar features con docs obsoletas

## Tests
- Tests en `tests/`. Runner: `pytest -q` (CI en cada push a `main`)
- **Antes de commitear cualquier cambio de comportamiento:** `grep -r "nombre_función_o_módulo" tests/` — si hay tests que cubren el código modificado, actualizarlos en el mismo commit. No commitear con tests que fallan o que verifican comportamiento ya obsoleto
- Si el comportamiento cambia (UX, API, lógica de clasificación, formato de mensajes), los tests de ese módulo son parte del cambio, no un afterthought

## Commits y deploy
- Al **cerrar una feature o fix** (tests OK, usuario confirma o scope claro): **commit + push a `main` sin pedir permiso**
- También al confirmar explícitamente ("funciona", "listo", "perfecto", "ok", "perfecto")
- Push dispara CI → deploy automático al server (`surehub-home`) si CI pasa
- NO commitear cambios triviales (typo, print de debug, ajuste de texto suelto)
- NO push si el usuario pide esperar o hay secretos en el diff
- Mensajes en inglés, formato: `<tipo>: <qué>` + body si el why no es obvio
- Tipos: `feat`, `fix`, `refactor`, `chore`

## Decisiones de arquitectura
- **SQLite en local y prod** — prod corre en el server homelab (`surehub-home`), DB canónica en `/srv/surehub/data/surehub.db`. `DATABASE_URL` apunta ahí; Postgres descartado por ahora (uso personal, SQLite sobra)
- **DB canónica = server**. El PC ya no corre SureHub (no arrancar `bot.run` en local con el mismo token → conflicto polling)
- Telegram polling en local, webhook en prod — cambio en TELEGRAM_MODE
- Bot y FastAPI corren como procesos separados en local, containers separados en prod (api/bot/frontend vía docker compose en el server)
- Claude API model: `claude-sonnet-4-6` — cambiar solo si hay razón explícita
- No hay historial de conversación en el bot — cada mensaje es independiente (decisión consciente, añadir si el uso real lo justifica)
- Memoria del bot: módulo SQLite + pantalla Memory en frontend. Ya no hay comandos Telegram; se inyecta solo en `/analisis` si hay hechos guardados
- Frontend consume API en /api (proxy Vite → FastAPI). En prod, mismo origen

## Bot Telegram

**Filosofía:** captura sin comando primero. Menú de autocompletado `/` mínimo (4 entradas).

**Menú** (`bot_commands()` en `help_text.py`): `help`, `mes`, `gastos`, `inbox`

**Captura sin comando**
- Gasto: `descripción cantidad` o `cantidad descripción` → categoría por keywords o botones inline
- Nota: texto libre (≥2 palabras), prefijo `. idea`, audio 🎤 → `{vault}/inbox/*.md`. Feedback: header con emoji (`📝` texto / `🎤` voz) + eco del texto + tags en línea aparte (`🏷️ Tags:` o `🏷️ sin tags`)
- Comandos ocultos del menú (siguen activos): `/nota`, `/note`, `/gastosid`, `/borrar`, `/categorias`, `/start`, `/ayuda`

**Consultas y acciones**
- `/mes` — resumen variable/fijo, variación vs mes anterior, alertas de presupuesto (absorbe el antiguo `/stats`)
- `/gastos` — últimos 10, o `/gastos mes` (sin id, lista limpia)
- `/gastosid` — igual que `/gastos` pero con el id de cada gasto para `/borrar` (oculto del menú, solo en `/help`)
- `/inbox` — escaneo + digest con botones; job diario a `INBOX_DIGEST_HOUR`
- `/analisis` — Claude Sonnet sobre finanzas del mes; **confirmación obligatoria** (inline) antes de llamar a la API; fuera del menú por coste

**Retirado del bot:** `/recuerda`, `/memoria`, `/olvidar`, `/generar`, `/stats`

**Obsidian:** todo pasa por `OBSIDIAN_VAULT_PATH`. Rutas: `inbox/`, `archivo/`, `inbox/_descartado/`, `Tareas.md`. Si mueves el vault: actualizar `.env` en prod, volumen Docker en homelab, reiniciar contenedor bot.

## Estado actual del módulo Inbox (Obsidian)

- Módulo `app/modules/inbox/` + handlers en `bot/inbox_handlers.py`
- Modelo `InboxItem` en SQLite (`inbox_items`): trackea cada `.md` visto en `inbox/` + propuesta IA + estado
- Clasificación Haiku vía `complete_tags` → `task` | `note` | `event` | `uncertain` (fallo LLM → `uncertain`, nunca se pierde la nota)
- Comando `/inbox`: escanea notas nuevas, envía digest Telegram con aprobación en lote
- Digest diario: `JobQueue.run_daily` a las `INBOX_DIGEST_HOUR` (default 9, `TIMEZONE`)
- Acciones reversibles (mover `.md`): `task` → línea en `Tareas.md` + `archivo/`; `note` → `archivo/`; `discard` → `inbox/_descartado/`
- Notas `uncertain` (o voz 🎤): botones individuales + flujo editar (siguiente mensaje de texto)
- Eventos (`event`): Sonnet extrae fecha/duración/temática (`extract_event` en `service.py`, 2ª llamada solo en notas-evento; fallo → la nota cae a `uncertain`). Tarjeta **individual** en el digest con fecha legible; `📅 Crear` → Google Calendar (`app/services/calendar.py`) con color por temática (`CALENDAR_COLORS`), nota → `archivo/`, status `scheduled`, guarda `calendar_event_id`, responde con link. `✏️ Editar fecha` re-extrae y reenvía la tarjeta. Sin comando Telegram (se gestiona desde el digest). Duración: explícita / inicio+fin / +1h default / all-day sin hora
- Google Calendar — **dos capas**: auth en `app/modules/calendar/` (OAuth **web flow**, token persistido en SQLite tabla `google_tokens`, refresh automático; expone `get_credentials`) + Calendar API en `app/services/calendar.py` (colores por temática, all-day; su `_service()` pide credenciales a la capa de auth). OAuth one-time: visitar `/api/calendar/oauth/init` vía túnel SSH a `localhost:8001` (Google no acepta IPs; ver redirect URI). Router `app/routers/calendar.py`: `oauth/init`, `oauth/callback`, `status`. Env: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `GOOGLE_CALENDAR_ID` (default `primary`). ⚠️ App Google en modo **Testing** → token expira a 7 días salvo verificación (en curso)
- Spec Fase 1: `docs/superpowers/specs/2026-06-18-inbox-auto-processing-design.md`
- Spec Fase 2 (hecho 2026-06-18): `docs/superpowers/specs/2026-06-18-inbox-calendar-events-design.md`

## Estado actual del módulo Finanzas
- Modelos: `Category` (name, type, monthly_estimate, active) + `Expense` (category_id FK, amount, description, date, source) + `RecurringExpense` (name, amount, category_id, day, active)
- `Category.active`: soft delete — categorías inactivas ocultas en UI pero los gastos históricos mantienen el FK
- Coste fijo = módulo recurrente (single source). Anuales (Google One, Amazon Prime) **prorrateados** = anual/12. Filas fijas enlazadas vía `recurring_id` para que `generate_recurring` no las duplique
- ⚠️ Subs anuales prorrateadas: **no anotar el cargo anual real** cuando caiga en el banco — el recurrente mensual ya lo cubre; anotarlo duplica
- Reembolsos (bizum recibido) se registran como ajuste negativo en `Varios` (decisión: no construir split-tracking; si crece → Firefly III)
- **Fechas en formato mixto** en la DB: csv con microsegundos (`...00:00:00.000000`), import sin ellos (`...00:00:00`), bot tz-aware (`...+00:00`). `_month_range` devuelve **bounds string** (no `datetime`) para comparar bien con los tres — con bound `datetime` se caían los gastos del día 1 a medianoche (ver `service.py`). No volver a tz-aware ahí
- Telegram parser detects "description amount" or "amount description" pattern, infers category by keywords
- Import source values: `telegram`, `manual`, `import`, `recurring`, `csv` (Coda)
- Gastos recurrentes: `generate_recurring()` vía API `/api/recurrentes/generate` o frontend — no hay `/generar` en Telegram
- API prefix: `/api/finance` (categories, expenses, summary, evolution, months, import)
- Ports: backend 8001, frontend 5174

## Infraestructura
- **Prod (actual):** server homelab `surehub-home` (Ubuntu, Tailscale). Docker compose: api (FastAPI interno) + bot (polling) + frontend (nginx `:8001`, proxya `/api`). DB SQLite canónica en volumen `/srv/surehub/data`. Auto-deploy on merge a main (`.github/workflows/deploy.yml`, gated por `ci`). Detalle en repo `SureKT/homelab` → `docs/surehub.md`
- Local dev: PC + 3 terminales (backend, bot, frontend) contra SQLite local — pero la verdad vive en el server
- Claude API: ~$5-15/mes uso personal moderado
