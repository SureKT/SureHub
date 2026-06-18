# Inbox Fase 2 — eventos → Google Calendar

_Diseño, 2026-06-18. Continúa `2026-06-18-inbox-auto-processing-design.md` (Fase 1)._

## Objetivo

Las notas con fecha/hora que Fase 1 deja como `uncertain` se vuelven una categoría
propia (`event`) que, **con tu aprobación individual**, crea un evento en Google
Calendar — con duración correcta y color según tu temática.

## Alcance

**Fase 2 (este spec):** categoría `event` + extracción de fecha/duración (Sonnet) +
creación de evento en Google Calendar vía OAuth + color por temática + tarjeta de
aprobación individual con editar-fecha.

**Fuera:** recurrencia, invitados, recordatorios custom, comando undo (el link al
evento basta para editar/borrar en Google), multi-calendario.

## Principios de seguridad (heredados de Fase 1)

1. **Nada irreversible sin aprobación.** El evento se crea solo al pulsar `📅 Crear`.
2. **Fallo de extracción de fecha → `uncertain`.** Nunca se crea un evento a ciegas.
3. **Reversible.** Crear evento es reversible (lo borras en Google); guardamos
   `calendar_event_id` + se responde con el link.
4. **Voz = revisable.** Las notas de voz ya se marcan; la fecha se muestra siempre en
   la tarjeta antes de crear.

## Arquitectura

Sin módulo nuevo. Se extiende el módulo `inbox` + se añade un servicio Calendar.

### Clasificación — categoría nueva

Categorías pasan de `task | note | uncertain` a **`task | note | event | uncertain`**.
Haiku (`complete_tags`, sin cambios de modelo) marca `event` cuando detecta fecha/hora.
`uncertain` sigue capturando lo verdaderamente ambiguo.

### Extracción de fecha/duración/temática — Sonnet, solo si `event`

Función nueva `extract_event(text, today)` en `app/services/llm.py`, modelo
`settings.LLM_MODEL` (Sonnet). Recibe el cuerpo de la nota + la fecha de hoy +
`settings.TIMEZONE`. Devuelve JSON:

```json
{ "summary": "...", "start": "ISO8601", "end": "ISO8601", "all_day": false, "theme": "padel" }
```

Reglas (en el prompt):

- **Duración explícita** ("reunión 2h", "dura 90 min") → `end = start + dur`.
- **Inicio + fin** ("de 18 a 20", "viernes 9-10:30") → start/end directos.
- **Solo hora de inicio** → `end = start + 1h`.
- **Sin hora** → `all_day=true`, `start`/`end` como fecha (sin hora).
- **Temática:** clasificar en una de `[coach, formacion, social, gimnasio, padel]`;
  si no encaja → `default`.

Fallo del LLM o JSON no parseable → la nota se queda `uncertain` (no `event`), nunca
se intenta crear.

### Servicio Calendar — `app/services/calendar.py`

Wrapper sobre `google-api-python-client`. Responsabilidad única: crear eventos.

- Carga credenciales OAuth desde `settings.GOOGLE_CALENDAR_TOKEN`; refresca el token
  solo (refresh token persistido). No hay flujo interactivo en runtime.
- `create_event(summary, start, end, all_day, color_id) -> (event_id, html_link)`.
- Calendario destino: `settings.GOOGLE_CALENDAR_ID` (default `primary`).
- Mapeo temática → color (constante en el módulo, fácil de editar):

```python
CALENDAR_COLORS = {
    "coach":     "3",   # Grape   — Diana/coach
    "formacion": "4",   # Flamingo — clase IA / proyectos de trabajo
    "social":    "5",   # Banana  — ocio con amigos
    "gimnasio":  "9",   # Blueberry — entreno rutinario
    "padel":     "10",  # Basil   — pádel / deporte de club
    "default":   "8",   # Graphite — sin categorizar
}
```

Colores restantes libres para futuras temáticas.

### Modelo de datos — campos nuevos en `InboxItem`

| campo | tipo | nota |
|---|---|---|
| `event_start` | str, null | ISO8601 (fecha u datetime) |
| `event_end` | str, null | ISO8601 |
| `all_day` | bool, default False | |
| `theme` | str, default "" | una de las claves de `CALENDAR_COLORS` |
| `calendar_event_id` | str, null | id devuelto por Google tras crear |

SQLite `ALTER TABLE ADD COLUMN` (sin perder datos). Status nuevo: `scheduled`.

### Flujo

```
scan inbox/*.md no vistos
  → Haiku clasifica
  → si category == event: Sonnet extract_event → rellena event_start/end/all_day/theme
       (fallo → category = uncertain)
  → InboxItem(status=pending)
  → DIGEST: event = tarjeta individual
  → [📅 Crear] → calendar.create_event(color) → mover .md a archivo/
       → status=scheduled, guarda calendar_event_id → responde con link
```

### Digest — UX Telegram

Cada `event` es una **tarjeta individual** (nunca en lote — la fecha es demasiado
crítica). Formato:

```
📅 Evento: {summary}  [{theme}]
{fecha legible}   ({all-day | HH:MM–HH:MM})
```

Botones: `[📅 Crear] [✏️ Editar fecha] [📄 Archivar] [✗ Descartar]`.

- **Crear** → crea en Calendar, mueve `.md` a `archivo/`, `status=scheduled`, guarda
  `calendar_event_id`, responde con el link al evento.
- **Editar fecha** → el bot pide texto corregido; al recibirlo re-ejecuta
  `extract_event`, actualiza el item y **re-muestra la tarjeta** para confirmar (no crea
  solo).
- **Archivar / Descartar** → reusan las acciones de Fase 1 (`note` / `discard`).

### Acciones y ciclo de vida del fichero

| Acción | Efecto |
|---|---|
| `event` (Crear) | Crear evento en Calendar + mover `.md` a `archivo/` + `status=scheduled` + guardar `calendar_event_id`. |
| `note` (Archivar) | Mover a `archivo/` (Fase 1). |
| `discard` | Mover a `inbox/_descartado/` (Fase 1). |
| `event` sin resolver | Queda `pending` en `inbox/` → reaparece en el próximo digest. |

### OAuth setup (one-time)

- `scripts/google_auth.py`: corre **una vez en local**, abre navegador (consent),
  guarda `token.json`. Reusa el refresh token después sin reautenticar.
- Requiere un **OAuth Client (Desktop)** creado en Google Cloud Console + Calendar API
  habilitada. Scope: `https://www.googleapis.com/auth/calendar.events`.

### Config (`app/config.py` + `.env.example`)

- `GOOGLE_CALENDAR_CREDENTIALS` — ruta al client secret JSON.
- `GOOGLE_CALENDAR_TOKEN` — ruta al token persistido (en prod: volumen
  `/srv/surehub/data`).
- `GOOGLE_CALENDAR_ID` — default `primary`.

### Dependencias

`google-api-python-client`, `google-auth`, `google-auth-oauthlib` (a
`requirements.txt`).

### Deploy (repo `SureKT/homelab`)

Montar `token.json` + client secret en el volumen del contenedor `bot`. Documentar en
`docs/surehub.md` del repo homelab. El token se genera en local y se sube al volumen
del server (no hay navegador en el server).

## Testing

- `extract_event`: parseo OK; duración explícita; inicio+fin; solo inicio → +1h; sin
  hora → all_day; temática fuera de lista → `default`; fallo LLM → la nota acaba
  `uncertain`.
- `calendar.create_event`: mockeado (no llamadas reales); pasa `colorId` correcto;
  all_day usa `date` vs timed usa `dateTime`.
- `apply_item` acción `event`: crea (calendar mockeado) + mueve `.md` + `status=scheduled`
  + guarda `calendar_event_id`.
- Editar fecha: re-ejecuta `extract_event` y actualiza el item.
- Bot: digest muestra tarjeta `event`; callback `Crear` invoca el servicio.
- Reusar `conftest` (engine in-memory) + `tmp_path` como vault + mock del servicio
  Calendar.

## Decisiones cerradas

- Categoría `event` propia (Fase 1 la dejaba en `uncertain`).
- Extracción con **Sonnet** (`LLM_MODEL`), 2ª llamada solo en notas-evento; coste
  ≈ $0.003/evento, despreciable.
- Aprobación **siempre individual** para eventos (fecha error-prone).
- Calendario **primary**.
- Color por temática vía `CALENDAR_COLORS` (mapeo fijo, editable en el módulo).
- Reversibilidad vía link al evento, sin comando undo (YAGNI).
- Duración: explícita / inicio+fin / +1h default / all-day sin hora.
</content>
</invoke>
