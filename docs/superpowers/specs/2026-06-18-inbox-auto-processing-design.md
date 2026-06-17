# Procesado automático de la inbox Obsidian — Fase 1

_Diseño, 2026-06-18. Modelo aprobado: A (digest + aprobación en lote)._

## Objetivo

Las notas capturadas por Telegram caen en `inbox/` del vault y se acumulan sin
procesar. La mayoría son **tareas** disfrazadas de nota. Esta feature las clasifica con
IA y, **siempre con tu aprobación en lote**, las convierte en tareas (Obsidian) o las
archiva — vaciando la inbox sin riesgo de actuar sobre basura/errores/mala transcripción.

## Alcance

**Fase 1 (este spec):** clasificación (tarea / nota / dudoso) + digest con aprobación
en lote + tarea→Obsidian Tasks + archivado + ciclo de vida de la nota. **Sin OAuth.**

**Fuera (Fase 2, spec aparte):** eventos → Google Calendar (OAuth). En Fase 1, una nota
con pinta de evento se clasifica como `dudoso` (se muestra, no se actúa).

## Principios de seguridad (la razón de existir del diseño)

1. **Nada irreversible sin aprobación.** El bot propone; tú apruebas/editas/descartas.
2. **Captura intacta.** Capturar sigue instantáneo; el procesado es un paso aparte.
3. **Movimientos reversibles.** Las acciones son mover/editar ficheros `.md` (git +
   Obsidian = historial). Descartar = mover a carpeta, nunca borrado duro.
4. **Voz = siempre revisable.** Notas `source: telegram-voice` se marcan en el digest
   (transcripción error-prone).

## Arquitectura

Nuevo módulo `app/modules/inbox/` (patrón estándar: `models.py` + `service.py`).

### Modelo de datos — `InboxItem` (SQLModel, registrar en `app/models.py`)

| campo | tipo | nota |
|---|---|---|
| `id` | int PK | |
| `filename` | str, unique, index | nombre del `.md` en inbox (identidad estable) |
| `excerpt` | str | primeros ~200 chars de la nota, para el digest |
| `source` | str | `telegram` / `telegram-voice` / … (del frontmatter) |
| `category` | str | `task` / `note` / `uncertain` |
| `proposed_text` | str | texto limpio propuesto (p.ej. la tarea normalizada) |
| `status` | str | `pending` / `approved` / `archived` / `discarded` |
| `created_at` | datetime | |
| `resolved_at` | datetime, null | cuándo se aplicó la acción |

La DB es la fuente de verdad de "qué notas ya vi". Escanear = ficheros en `inbox/`
cuyo `filename` no está en `InboxItem`.

### Flujo

```
/inbox (on-demand)  ó  job diario
  → scan inbox/*.md no vistos
  → por cada uno: clasificar con IA → crear InboxItem(status=pending)
  → enviar DIGEST a Telegram (items pending: nuevos + los que seguían pendientes)
  → usuario aprueba/edita/descarta (botones)
  → aplicar acción + status + mover fichero
```

### Clasificación (IA)

- Función nueva en `app/services/llm.py` (estilo `complete_tags`, modelo barato = Haiku):
  entra el cuerpo de la nota, sale JSON `{category, proposed_text}`.
- Categorías Fase 1: `task` | `note` | `uncertain`.
- Heurística de seguridad: nota muy corta, sin verbo accionable, o con pinta de evento
  (fecha/hora) → `uncertain`. Notas de voz → marcar en el digest (no cambia categoría).
- Fallo del LLM → `uncertain` (nunca se pierde ni se actúa a ciegas).

### Digest — UX Telegram

- Si no hay pendientes: "Inbox limpia ✅".
- Cabecera: "N notas sin procesar".
- **Lote para lo confiable:** lista de `task`/`note` propuestos + botón único
  **"✓ Aplicar sugeridos"** (las aplica todas de una).
- **Individual para lo dudoso:** cada `uncertain` con sus botones
  `[✓ Tarea] [📄 Archivar] [✗ Descartar] [✏️ Editar]`.
- Editar = el bot pide el texto corregido (siguiente mensaje) y reusa la acción.
- Reusa el patrón de callbacks existente (`cmd_borrar` / `callback_categoria`).

### Acciones y ciclo de vida del fichero

| Categoría aprobada | Acción |
|---|---|
| `task` | Añadir línea `- [ ] {proposed_text}  ([[{filename}]])` a `Tareas.md` del vault. Mover la nota de `inbox/` a `archivo/`. |
| `note` (archivar) | Mover la nota de `inbox/` a `archivo/`. |
| `discard` | Mover a `inbox/_descartado/` (reversible, no borrado). |
| `uncertain` sin resolver | Queda en `inbox/` y en DB como `pending` → reaparece en el próximo digest. |

`Tareas.md` en formato **Obsidian Tasks** (`- [ ]`), con backlink a la nota origen.
Lo gestionas/marcas hecho desde la app de Obsidian en el móvil (Syncthing).

### Programación

- **On-demand:** comando bot `/inbox` (lanza scan + digest ahora).
- **Diario:** `JobQueue` de python-telegram-bot (`run_daily`), hora configurable. Sin
  scheduler externo.

### Config (`app/config.py` + `.env.example`)

- `INBOX_DIGEST_HOUR` (default `9`) — hora del digest diario.
- Rutas derivadas de `OBSIDIAN_VAULT_PATH`: `inbox/`, `archivo/`, `inbox/_descartado/`,
  `Tareas.md`. (Constantes en el módulo; no hace falta env por cada una.)

## Testing

- `service`: scan ignora ya-vistos; clasificación parseada (mock LLM); fallo LLM →
  `uncertain`; aplicar `task` añade línea a `Tareas.md` + mueve fichero; `discard` mueve a
  `_descartado`; `note` archiva.
- `bot`: `/inbox` sin pendientes → "Inbox limpia"; con pendientes → manda digest;
  callback "aplicar sugeridos" aplica el lote; editar reusa la acción.
- Reusar `conftest` (engine in-memory) + `tmp_path` como vault.

## Decisiones cerradas

- Tareas → Obsidian Tasks (no dashboard, no app externa).
- Recordatorios → **no hay categoría propia** (YAGNI): con hora = evento (Fase 2), sin
  hora = tarea con fecha.
- Eventos → Fase 2 (Google Calendar / OAuth).

## Preguntas abiertas (no bloquean Fase 1)

- ¿`Tareas.md` único o por área/fecha? (arranco con único; Dataview ya filtra).
- ¿Modelo de clasificación Haiku vs Sonnet? (arranco Haiku por coste; subir si falla).
