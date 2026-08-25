# Backlog SureHub

Único fichero de pendientes/ideas (antes había TODO.md + BACKLOG.md duplicados).
La sesión de Claude Code (server, Remote Control) lo mantiene: pedir "apunta esto
al backlog" o "marca X hecho" desde el móvil. El registro de lo *hecho* es el `git log`;
aquí solo hitos si hace falta contexto.

> Filtrar siempre por el roadmap "no reinventar la rueda" (ver `CLAUDE.md`): no
> construir lo ya resuelto por Obsidian / Khoj / Firefly III.

## En curso

- [ ] **LLM Routing — Fase 3 (evals)** — `evals/` (dataset tagging real + `promptfooconfig.yaml`),
  local vs Haiku vs Sonnet, report + regla de decisión (local accuracy ≥ Haiku−5pp → mantener local).

## Pendiente — módulos

- [ ] **Noticias** — bandeja de entrada, temas de interés configurables
- [ ] **Correo** — Gmail, resumen con Claude, reglas (filtros/etiquetas), automatizaciones
- [ ] **Análisis documentos** — ingesta (PDF, etc.), resumen con Claude, automatizaciones por contenido

## Pendiente — mejoras

- [ ] **Finanzas** — gráficos más ricos (evolución por categoría, comparativa meses)
- [ ] **App shell** — login + gestión de credenciales/API keys de servicios externos
- [ ] **App shell** — dual sidebar (izq nav global · dcha config módulo/explorar; ref Coda/Notion/VSCode), cuando los módulos tengan contenido secundario suficiente

## Hecho

- [x] **LLM Routing — Fase 2 (Ollama local)** (2026-08-25) — container `ollama` en el server
  (CPU, red `ollama-net`) + `qwen2.5:3b`. `TIERS["local_ok"]` = local → fallback Haiku, con
  timeout y fallback manual en el router. Verificado end-to-end: local sirve (`fell_back=false`,
  coste 0) y con Ollama parado cae a Haiku (`fell_back=true`). Latencia CPU: tags ~1-1,5 s,
  clasificación ~2-3 s. Infra: `SureKT/homelab` → `docs/ollama.md`.
- [x] **LLM Routing — Fase 1** (mergeada + deployada 2026-06-29) — capa LiteLLM (`app/services/llm_router.py`,
  tier→modelo + fallback) + log SQLite `llm_calls`. `app/services/llm.py` mantiene interfaz. Validada
  end-to-end contra la API real (cloud→Sonnet, local_ok→Haiku) con la key de prod; corregido falso
  positivo de `fell_back` por snapshot con fecha. Prod corre con litellm. Spec/plan:
  `docs/superpowers/{specs,plans}/2026-06-26-llm-routing-evals*`.
- [x] **Inbox Fase 2** (2026-06-18) — eventos con fecha/hora → Google Calendar (OAuth
  one-time). Categoría `event`, extracción Sonnet (fecha/duración/temática), color por
  temática, tarjeta individual con editar-fecha. Spec:
  `docs/superpowers/specs/2026-06-18-inbox-calendar-events-design.md`.
- [x] **Inbox Fase 1** (2026-06-18) — clasificación IA + digest Telegram + tareas→`Tareas.md` +
  archivado. Comando `/inbox`, job diario `INBOX_DIGEST_HOUR`. Spec:
  `docs/superpowers/specs/2026-06-18-inbox-auto-processing-design.md`.
- [x] **Spotify — frontend** — Spotify.jsx + Settings.jsx + light theme.
- [x] **Infra prod** — desplegado en homelab `surehub-home` (Docker compose, SQLite canónica,
  auto-deploy on merge). Descartado: Hetzner VPS y migración Postgres (SQLite sobra para uso personal).
