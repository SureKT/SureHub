# SureHub

Plataforma personal modular: finanzas, noticias, automatizaciones, agente IA.
Stack: FastAPI + SQLModel + SQLite/Postgres + Telegram bot + Claude API.

## Comandos
- Backend: `uvicorn app.main:app --reload` (desde raíz, venv activado)
- Bot: `python -m bot.run` (segunda terminal, venv activado)

## Estructura
```
app/
  modules/<modulo>/
    models.py    # SQLModel table models
    service.py   # lógica de negocio, recibe Session
    parser.py    # parsing de input (si aplica)
  services/
    llm.py       # wrapper Claude API
  config.py      # Settings desde .env
  database.py    # engine, get_session, create_db
  models.py      # importa todos los modelos (para create_db)
  main.py        # FastAPI app
bot/
  handlers.py    # handlers de Telegram
  run.py         # arranque del bot
```

## Convenciones
- Nombres en español (dominio del negocio), código en inglés solo si es técnico puro
- Nuevos módulos siempre en `app/modules/<modulo>/` con models + service
- Registrar modelo nuevo en `app/models.py` para que create_db() lo cree
- `get_session()` con `next()` en handlers — no usar como context manager en sync code
- Variables de entorno: siempre en `.env`, nunca hardcodeadas, documentar en `.env.example`
- Sin comentarios obvios — solo si el WHY no es evidente

## Commits
- Hacer commit cuando una feature funcione y haya contenido suficiente para justificarlo
- Si el usuario confirma que algo funciona ("funciona", "listo", "perfecto") y hay cambios staged → proponer o hacer commit directamente
- Mensajes en inglés, formato: `<tipo>: <qué> + detalle en body si aplica`
- Tipos: `feat`, `fix`, `refactor`, `chore`

## Decisiones de arquitectura
- SQLite en local, Postgres en prod — cambio solo en DATABASE_URL
- Telegram polling en local, webhook en prod — cambio en TELEGRAM_MODE
- Bot y FastAPI corren como procesos separados en local, mismo container en prod
- Claude API model: `claude-sonnet-4-6` — cambiar solo si hay razón explícita
