# SureHub

Plataforma personal modular: finanzas, noticias, automatizaciones, agente IA.
Usuario único: Sure (uso doméstico, sin auth, sin multiusuario).
Stack: FastAPI + SQLModel + SQLite/Postgres + Telegram bot + Claude API.

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
  run.py         # arranque del bot (llama a create_db al inicio)
frontend/        # React + Vite, proxy /api → localhost:8000
scripts/         # scripts de migración y seed (uso puntual, no producción)
```

## Convenciones
- Nombres en español (dominio del negocio), código en inglés solo si es técnico puro
- Nuevos módulos siempre en `app/modules/<modulo>/` con models + service
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
- SQLite en local, Postgres en prod — cambio solo en DATABASE_URL
- Telegram polling en local, webhook en prod — cambio en TELEGRAM_MODE
- Bot y FastAPI corren como procesos separados en local, mismo container en prod
- Claude API model: `claude-sonnet-4-6` — cambiar solo si hay razón explícita
- No hay historial de conversación en el bot — cada mensaje es independiente (decisión consciente, añadir si el uso real lo justifica)
- Memoria del bot: manual vía /recuerda. Se inyecta en system prompt de Claude
- Frontend consume API en /api (proxy Vite → FastAPI). En prod, mismo origen

## Estado actual del módulo Finanzas
- Modelos: `Categoria` (nombre, tipo, estimacion_mensual, activa) + `Gasto` (categoria_id FK, cantidad, descripcion, fecha, fuente)
- `Categoria.activa`: borrado suave — inactivas no aparecen en UI pero gastos históricos conservan FK
- Categorías inactivas existentes: Anillo, Ahorros (datos históricos de Coda)
- 482 gastos históricos importados desde Coda (junio 2025 → marzo 2026)
- Parser de Telegram detecta patrón "descripcion cantidad" o "cantidad descripcion" e infiere categoría por keywords
- Faltas de categoría en import: multas → Varios, farmacia/dentista → Salud

## Módulos pendientes (por orden de prioridad acordado)
1. Mejoras dashboard finanzas (en curso)
2. Noticias/briefings (aparcado hasta nuevo aviso)
3. MCP server propio
4. Automatizaciones

## Infraestructura objetivo
- Local ahora: PC + 3 terminales (backend, bot, frontend)
- Prod futuro: Hetzner VPS ~€4/mes, Docker, webhook Telegram, Postgres
- Claude API: ~$5-15/mes uso personal moderado
