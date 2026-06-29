# Backlog SureHub

Único fichero de pendientes/ideas (antes había TODO.md + BACKLOG.md duplicados).
La sesión de Claude Code (server, Remote Control) lo mantiene: pedir "apunta esto
al backlog" o "marca X hecho" desde el móvil. El registro de lo *hecho* es el `git log`;
aquí solo hitos si hace falta contexto.

> Filtrar siempre por el roadmap "no reinventar la rueda" (ver `CLAUDE.md`): no
> construir lo ya resuelto por Obsidian / Khoj / Firefly III.

## En curso

- [ ] **LLM Routing — Fase 1 validada end-to-end, lista para merge a `main`** (rama
  `feat/llm-routing-evals`, validada 2026-06-29). Llamada real LiteLLM→Anthropic confirmada con la
  key de prod (extraída del container `surehub-api-1`): `cloud`→Sonnet y `local_ok`→Haiku devuelven
  texto, coste y tokens reales. Bug encontrado y corregido: Anthropic resuelve el alias a snapshot
  con fecha (`claude-haiku-4-5-20251001`), `_base()` lo marcaba como fallback falso → ahora compara
  con `startswith`. Plan: `docs/superpowers/plans/2026-06-26-llm-routing-evals.md`.
- [ ] **LLM Routing — Fase 2 (Ollama local)** — instalar Ollama en `surehub-home` (CPU), pull
  `qwen2.5:3b`, validar `ollama_chat/<model>` + `OLLAMA_BASE_URL`, prepend local a `TIERS["local_ok"]`
  con timeout, verificar fallback (matar Ollama → cae a Haiku, log `fell_back=true`). Plan propio tras Fase 1.
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
