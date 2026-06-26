# LLM routing + evals — diseño

**Fecha:** 2026-06-26
**Estado:** aprobado (pendiente review escrito)
**Driver:** aprendizaje LLMOps + portfolio + privacidad/independencia. **No** coste (volumen bajo: $5-15/mes). Decisión consciente — ver "No-objetivos".

## Resumen

SureHub deja de llamar a la SDK de Anthropic directamente. Pasa a llamar vía
**LiteLLM**, que abstrae el proveedor y permite enrutar cada llamada por *tier*
a un backend local (**Ollama**) o cloud (**Claude**) con **fallback**. Cada
llamada se loguea a **SQLite**. Un **eval offline con promptfoo** sobre tareas
reales de SureHub decide, con datos, qué tareas puede asumir el modelo local.

## Principio rector: permanente mínimo vs experimento

- **Permanente** (corre para años, mantenimiento ≈ cero): LiteLLM en `llm.py` +
  logging SQLite.
- **Experimento** (time-boxed, se queda el conocimiento + el informe, no infra
  fija): Ollama + promptfoo. El routing a local **solo se mantiene si los evals
  lo justifican**. Si no, se documenta el aprendizaje y se vuelve a cloud.

## Objetivos

1. Abstraer la capa LLM de SureHub tras LiteLLM (agnóstica de proveedor,
   fallback, un solo punto para añadir modelos).
2. Observabilidad durable: cada llamada LLM registrada (backend, tokens, coste,
   latencia, prompt, output) en SQLite.
3. Aprender LLMOps construyendo un eval real: comparar local vs Haiku vs Sonnet
   sobre clasificación de tags/gastos de SureHub, con métricas.
4. Decisión de routing **basada en datos**, no a ojo.
5. Posibilidad de correr la tarea de tags 100% local (privacidad) si la calidad
   aguanta.

## No-objetivos (v1)

- **Langfuse / observabilidad como servicio.** A este volumen, SQLite basta.
  Fuera para no añadir infra permanente a un server que debe durar años.
- **Ahorro de coste como justificación.** El volumen no lo sostiene.
- **Setup GPU (driver NVIDIA/CUDA en la 1650).** v1 corre Ollama en CPU. GPU =
  mejora futura opcional, su propia tarea.
- **Routing heurístico** (inspeccionar el prompt para elegir). v1 usa política
  explícita por llamada.
- **Cambios de streaming** en el bot.

## Arquitectura

```
SureHub (app/services/llm.py)
  chat()           tier="cloud"
  complete_tags()  tier="local_ok"
  complete_event() tier="cloud"
        │
        ▼
  LiteLLM (completion + Router con fallbacks)
        │  ── callback ──►  SQLite (tabla llm_calls)
        ▼
   tier "local_ok": [ollama_chat/<modelo>]  ──fallback──► [anthropic/haiku]
   tier "cloud":    [anthropic/sonnet]  (o haiku según función)

  promptfoo (offline, dev) ── compara providers sobre dataset real ──► informe
```

## Componentes

### 1. `app/services/llm.py` (modificado)
Mantiene las **mismas 3 funciones públicas** (`chat`, `complete_tags`,
`complete_event`) — los call-sites (`handlers.py`, `inbox_handlers.py`) no
cambian. Internamente:
- Sustituye `client.messages.create(...)` por `litellm.completion(...)`.
- Cada función declara su **tier**. El tier→lista-de-modelos vive en config.
- Envuelve la llamada con el logger (registra siempre, éxito o error).

### 2. `app/services/llm_router.py` (nuevo)
- Config tier→modelos (primary + fallbacks) leída de `settings`.
- `complete(messages, tier, **opts) -> Result`: resuelve modelos del tier, llama
  vía LiteLLM con fallback y timeout, devuelve texto + metadata (modelo servido,
  tokens, coste, latencia, si hubo fallback).
- Timeout local configurable (ej. 20s) → si expira o falla, LiteLLM cae al
  fallback cloud.

### 3. `app/modules/llm_log/` (nuevo: model + service)
- `LLMCall` (tabla `llm_calls`): `id, ts, function, tier, model_requested,
  model_served, fell_back, input_tokens, output_tokens, cost_usd, latency_ms,
  prompt, output, success, error`.
- Registrado en `app/models.py` para `create_db()`.
- Vista mínima de lectura (frontend o endpoint) — opcional en v1, basta la tabla.

### 4. `evals/` (nuevo, dev-only — no corre en prod)
- `dataset.jsonl`: casos reales de tagging/clasificación con etiqueta esperada
  (anonimizados).
- `promptfooconfig.yaml`: providers (ollama, anthropic/haiku, anthropic/sonnet),
  prompts, asserts (match de tag/categoría + rúbrica LLM si aplica).
- `README.md`: cómo correr el eval + el **informe de resultados** (artefacto de
  portfolio).

### 5. Infra (repo `SureKT/homelab`)
- Instalar y correr **Ollama** en `surehub-home` (CPU). Modelo candidato:
  `qwen2.5:3b` o `llama3.2:3b` (caben en RAM, buenos en clasificación corta).
- Documentar en `docs/surehub.md` o nuevo `docs/ollama.md`.

## Config (`.env` / `settings`)

```
LLM_ROUTER_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
LLM_LOCAL_TIMEOUT=20
TIER_LOCAL_OK=ollama_chat/qwen2.5:3b,anthropic/claude-haiku-...   # primary,fallback
TIER_CLOUD=anthropic/claude-sonnet-4-...
```
Documentar en `.env.example`. Mapeo concreto de tiers se ajusta tras el eval.

## Flujo de datos

1. Caller llama `complete_tags(prompt)`.
2. `llm.py` invoca `router.complete(msgs, tier="local_ok")`.
3. Router resuelve `[ollama local, haiku fallback]`, llama vía LiteLLM con
   timeout.
4. Local responde (o falla → fallback a Haiku).
5. Logger escribe fila en `llm_calls` (modelo servido, fell_back, métricas).
6. Devuelve texto al caller (interfaz idéntica a hoy).

## Manejo de errores / fallback

- **Local caído / timeout / error:** LiteLLM Router cae al fallback cloud. Se
  loguea `fell_back=true`.
- **Cloud también falla:** propaga excepción; el caller ya degrada
  graciosamente (en inbox, nota → `uncertain`, nunca se pierde — comportamiento
  actual intacto).
- **Logger nunca rompe la llamada:** si falla el insert, se traga el error y se
  loguea aparte (la respuesta LLM es lo prioritario).

## Fases (incrementales, cada una desplegable)

1. **Observabilidad + abstracción.** LiteLLM en `llm.py` + tabla `llm_calls` +
   logger. **Todo sigue a cloud** (tier_local_ok = haiku de momento).
   Comportamiento sin cambios visibles. Valor: ves coste/latencia reales.
2. **Backend local + routing.** Instalar Ollama + modelo. `complete_tags` →
   primary local, fallback Haiku. Timeout + fallback verificados.
3. **Eval + decisión.** `evals/` con dataset real + promptfoo. Comparar local
   vs Haiku vs Sonnet. **Criterio:** si accuracy local ≥ (Haiku − 5pp) en
   tagging → se mantiene routing a local. Si no → revertir tier a cloud,
   conservar informe. Documentar conclusión.

## Testing

- **Unit:** `router.complete` resuelve tier→modelos correcto; fallback (mock de
  fallo local → sirve cloud); logger inserta fila con campos correctos.
- **Mock de LiteLLM** en tests → sin red, CI verde sin Ollama ni API key.
- **Smoke (manual / skip si no hay Ollama):** llamada real local end-to-end.
- Actualizar tests existentes de `inbox`/`handlers` si cambia algo observable
  (no debería — interfaz pública igual). `grep -r complete_tags tests/`.

## Riesgos

- **3B en CPU lento** (¿segundos por tag?). Mitiga: tarea no urgente (tags), y
  el timeout+fallback evita bloqueos. Si molesta → GPU (fase futura) o revertir.
- **Calidad local insuficiente** → es justo lo que el eval mide; revertir es un
  resultado válido, no un fallo.
- **Naming de modelos LiteLLM** (anthropic/ollama_chat prefixes) — validar en
  fase 1 con una llamada real.

## Artefactos de portfolio resultantes

- Capa LLM agnóstica con fallback (código).
- Informe de evals local vs cloud sobre workload real (`evals/README.md`).
- Decisión de routing documentada con datos.
- Entrada en homelab: Ollama self-hosted con propósito.
