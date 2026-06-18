# Inbox Fase 2 — Eventos → Google Calendar — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Notas con fecha/hora se clasifican como `event`, se extrae fecha/duración/temática con Sonnet, y con aprobación individual se crean en Google Calendar con color por temática.

**Architecture:** Se extiende el módulo `inbox` (clasificación + acciones) y se añade un servicio Calendar (`app/services/calendar.py`) con wrapper OAuth de `google-api-python-client`. La extracción de fecha es una 2ª llamada LLM (Sonnet) solo en notas-evento; la creación del evento la dispara el usuario desde una tarjeta individual de Telegram. Fallo de extracción → la nota cae a `uncertain` (nunca se crea a ciegas).

**Tech Stack:** FastAPI/SQLModel/SQLite, python-telegram-bot, Anthropic (Haiku clasifica, Sonnet extrae), google-api-python-client + google-auth(-oauthlib).

---

## File Structure

- `requirements.txt` — añade libs Google.
- `app/config.py` — 3 settings nuevas (`GOOGLE_CALENDAR_*`).
- `app/modules/inbox/models.py` — 5 campos nuevos en `InboxItem` + status `scheduled`.
- `app/services/llm.py` — `complete_event(prompt)` (Sonnet).
- `app/modules/inbox/service.py` — `extract_event`, categoría `event` en clasificación y scan, `apply_event`.
- `app/services/calendar.py` — NUEVO: `CALENDAR_COLORS`, `_event_body` (puro, testeable), `create_event` (wrapper Google, imports lazy).
- `bot/inbox_handlers.py` — tarjeta de evento en digest, callbacks `event`/`editdate`, `reextract_event_date`.
- `bot/handlers.py` — despacho de texto para editar-fecha.
- `scripts/google_auth.py` — NUEVO: OAuth one-time.
- Tests: `tests/test_inbox_service.py`, `tests/test_calendar_service.py` (NUEVO), `tests/test_inbox_handlers.py`.
- Docs: `CLAUDE.md`, `.env.example`, `docs/architecture.md`, `docs/BACKLOG.md`.

---

## Task 1: Dependencias y config

**Files:**
- Modify: `requirements.txt`
- Modify: `app/config.py:30-38` (bloque LLM, añadir antes/después)
- Modify: `.env.example`

- [ ] **Step 1: Añadir libs Google a requirements.txt**

Añade al final de `requirements.txt`:

```
google-api-python-client>=2.130.0
google-auth>=2.30.0
google-auth-oauthlib>=1.2.0
```

- [ ] **Step 2: Instalar**

Run: `pip install -r requirements.txt`
Expected: instala las 3 libs sin error.

- [ ] **Step 3: Añadir settings a app/config.py**

En la clase `Settings`, tras el bloque LLM (`TAG_MODEL`), añade:

```python
    # Google Calendar (Inbox Fase 2 — eventos)
    GOOGLE_CALENDAR_CREDENTIALS: str = "./data/google_client_secret.json"
    GOOGLE_CALENDAR_TOKEN: str = "./data/google_token.json"
    GOOGLE_CALENDAR_ID: str = "primary"
```

- [ ] **Step 4: Documentar en .env.example**

Añade al `.env.example` (sección nueva):

```
# Google Calendar (Inbox Fase 2). Genera el token con: python scripts/google_auth.py
# En prod: rutas dentro del volumen /srv/surehub/data
GOOGLE_CALENDAR_CREDENTIALS=./data/google_client_secret.json
GOOGLE_CALENDAR_TOKEN=./data/google_token.json
GOOGLE_CALENDAR_ID=primary
```

- [ ] **Step 5: Verificar que importa**

Run: `python -c "from app.config import settings; print(settings.GOOGLE_CALENDAR_ID)"`
Expected: `primary`

- [ ] **Step 6: Commit**

```bash
git add requirements.txt app/config.py .env.example
git commit -m "feat(inbox): google calendar deps and config"
```

---

## Task 2: Campos nuevos en InboxItem

**Files:**
- Modify: `app/modules/inbox/models.py`
- Test: `tests/test_inbox_service.py`

- [ ] **Step 1: Escribir test que falla**

Añade a `tests/test_inbox_service.py`:

```python
def test_inbox_item_has_event_fields(session):
    item = InboxItem(
        filename="ev.md", category="event", proposed_text="pádel con Marc",
        event_start="2026-06-20T18:00:00", event_end="2026-06-20T19:30:00",
        all_day=False, theme="padel",
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    assert item.event_start == "2026-06-20T18:00:00"
    assert item.theme == "padel"
    assert item.all_day is False
    assert item.calendar_event_id is None
```

- [ ] **Step 2: Run test, verificar que falla**

Run: `pytest tests/test_inbox_service.py::test_inbox_item_has_event_fields -v`
Expected: FAIL — `TypeError: 'event_start' is an invalid keyword argument`.

- [ ] **Step 3: Añadir campos al modelo**

En `app/modules/inbox/models.py`, dentro de `InboxItem`, tras `proposed_text`:

```python
    event_start: Optional[str] = None    # ISO local: 'YYYY-MM-DDTHH:MM:SS' o 'YYYY-MM-DD'
    event_end: Optional[str] = None
    all_day: bool = False
    theme: str = ""                       # clave de CALENDAR_COLORS
    calendar_event_id: Optional[str] = None
```

Y actualiza el comentario de `status` para incluir `scheduled`:

```python
    status: str = "pending"  # pending | approved | archived | discarded | scheduled
```

- [ ] **Step 4: Run test, verificar que pasa**

Run: `pytest tests/test_inbox_service.py::test_inbox_item_has_event_fields -v`
Expected: PASS

- [ ] **Step 5: Migración en server (nota, no ejecutar ahora)**

SQLite añade columnas sin perder datos. En el server, tras deploy, las columnas nuevas se crean vía `create_db()` solo en tablas nuevas — para una tabla existente hay que correr una vez:

```sql
ALTER TABLE inbox_items ADD COLUMN event_start TEXT;
ALTER TABLE inbox_items ADD COLUMN event_end TEXT;
ALTER TABLE inbox_items ADD COLUMN all_day BOOLEAN DEFAULT 0;
ALTER TABLE inbox_items ADD COLUMN theme TEXT DEFAULT '';
ALTER TABLE inbox_items ADD COLUMN calendar_event_id TEXT;
```

Documentar este SQL en el commit body (se aplica manualmente en prod tras el deploy).

- [ ] **Step 6: Commit**

```bash
git add app/modules/inbox/models.py tests/test_inbox_service.py
git commit -m "feat(inbox): event fields on InboxItem

Prod migration (run once on /srv/surehub/data/surehub.db):
  ALTER TABLE inbox_items ADD COLUMN event_start TEXT;
  ALTER TABLE inbox_items ADD COLUMN event_end TEXT;
  ALTER TABLE inbox_items ADD COLUMN all_day BOOLEAN DEFAULT 0;
  ALTER TABLE inbox_items ADD COLUMN theme TEXT DEFAULT '';
  ALTER TABLE inbox_items ADD COLUMN calendar_event_id TEXT;"
```

---

## Task 3: Servicio Calendar — `_event_body` puro

**Files:**
- Create: `app/services/calendar.py`
- Test: `tests/test_calendar_service.py`

- [ ] **Step 1: Escribir test que falla**

Crea `tests/test_calendar_service.py`:

```python
from app.services.calendar import _event_body, CALENDAR_COLORS


def test_timed_event_body_uses_datetime_and_color():
    body = _event_body("Pádel", "2026-06-20T18:00:00", "2026-06-20T19:30:00", False, "padel")
    assert body["summary"] == "Pádel"
    assert body["colorId"] == CALENDAR_COLORS["padel"]
    assert body["start"]["dateTime"] == "2026-06-20T18:00:00"
    assert body["end"]["dateTime"] == "2026-06-20T19:30:00"
    assert "timeZone" in body["start"]


def test_all_day_event_body_uses_exclusive_end_date():
    body = _event_body("Cumple", "2026-06-25", "2026-06-25", True, "social")
    assert body["start"]["date"] == "2026-06-25"
    # Google all-day end es exclusivo → +1 día
    assert body["end"]["date"] == "2026-06-26"
    assert body["colorId"] == CALENDAR_COLORS["social"]


def test_unknown_theme_falls_back_to_default_color():
    body = _event_body("X", "2026-06-25", "2026-06-25", True, "inexistente")
    assert body["colorId"] == CALENDAR_COLORS["default"]
```

- [ ] **Step 2: Run test, verificar que falla**

Run: `pytest tests/test_calendar_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.calendar'`.

- [ ] **Step 3: Crear app/services/calendar.py**

```python
from datetime import date, timedelta

from app.config import settings

# Mapeo temática → colorId de Google Calendar (eventColors). Editable a mano.
CALENDAR_COLORS = {
    "coach":     "3",   # Grape    — Diana/coach
    "formacion": "4",   # Flamingo — clase IA / proyectos de trabajo
    "social":    "5",   # Banana   — ocio con amigos
    "gimnasio":  "9",   # Blueberry — entreno rutinario
    "padel":     "10",  # Basil    — pádel / deporte de club
    "default":   "8",   # Graphite — sin categorizar
}

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def _event_body(summary: str, start: str, end: str, all_day: bool, theme: str) -> dict:
    color = CALENDAR_COLORS.get(theme, CALENDAR_COLORS["default"])
    body = {"summary": summary, "colorId": color}
    if all_day:
        end_excl = (date.fromisoformat(end) + timedelta(days=1)).isoformat()
        body["start"] = {"date": start}
        body["end"] = {"date": end_excl}
    else:
        body["start"] = {"dateTime": start, "timeZone": settings.TIMEZONE}
        body["end"] = {"dateTime": end, "timeZone": settings.TIMEZONE}
    return body


def _service():
    # Imports lazy: las libs Google solo se cargan en runtime, no en tests del body.
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(settings.GOOGLE_CALENDAR_TOKEN, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def create_event(summary: str, start: str, end: str, all_day: bool, theme: str) -> tuple[str, str]:
    """Crea el evento en Google Calendar. Devuelve (event_id, html_link)."""
    body = _event_body(summary, start, end, all_day, theme)
    ev = _service().events().insert(
        calendarId=settings.GOOGLE_CALENDAR_ID, body=body
    ).execute()
    return ev["id"], ev.get("htmlLink", "")
```

- [ ] **Step 4: Run test, verificar que pasa**

Run: `pytest tests/test_calendar_service.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/calendar.py tests/test_calendar_service.py
git commit -m "feat(calendar): event body builder and create_event wrapper"
```

---

## Task 4: Extracción de evento con Sonnet (`extract_event`)

**Files:**
- Modify: `app/services/llm.py`
- Modify: `app/modules/inbox/service.py`
- Test: `tests/test_inbox_service.py`

- [ ] **Step 1: Añadir `complete_event` a llm.py**

En `app/services/llm.py`, tras `complete_tags`:

```python
def complete_event(prompt: str) -> str:
    """Extracción de fecha/hora de eventos — Sonnet (mejor con fechas relativas)."""
    response = client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
```

- [ ] **Step 2: Escribir tests que fallan**

Añade a `tests/test_inbox_service.py` (y añade `extract_event` al import desde `app.modules.inbox.service`):

```python
from app.modules.inbox.service import extract_event  # añadir al bloque de imports


def test_extract_event_timed():
    llm = lambda p: '{"summary":"Pádel con Marc","start":"2026-06-20T18:00:00","end":"2026-06-20T19:00:00","all_day":false,"theme":"padel"}'
    data = extract_event("pádel con Marc el viernes a las 18", "2026-06-18 (jueves)", llm)
    assert data["summary"] == "Pádel con Marc"
    assert data["start"] == "2026-06-20T18:00:00"
    assert data["end"] == "2026-06-20T19:00:00"
    assert data["all_day"] is False
    assert data["theme"] == "padel"


def test_extract_event_all_day_defaults_end_to_start():
    llm = lambda p: '{"summary":"Cumple Ana","start":"2026-06-25","end":"","all_day":true,"theme":"social"}'
    data = extract_event("cumple de Ana el 25", "2026-06-18 (jueves)", llm)
    assert data["all_day"] is True
    assert data["end"] == "2026-06-25"  # end vacío → start


def test_extract_event_unknown_theme_becomes_default():
    llm = lambda p: '{"summary":"X","start":"2026-06-25","end":"2026-06-25","all_day":true,"theme":"viaje"}'
    assert extract_event("x", "2026-06-18", llm)["theme"] == "default"


def test_extract_event_llm_failure_returns_none():
    def llm(p):
        raise RuntimeError("API down")
    assert extract_event("x", "2026-06-18", llm) is None


def test_extract_event_non_json_returns_none():
    assert extract_event("x", "2026-06-18", lambda p: "no soy json") is None


def test_extract_event_missing_start_returns_none():
    llm = lambda p: '{"summary":"X","start":"","end":"","all_day":false,"theme":"padel"}'
    assert extract_event("x", "2026-06-18", llm) is None
```

- [ ] **Step 3: Run tests, verificar que fallan**

Run: `pytest tests/test_inbox_service.py -k extract_event -v`
Expected: FAIL — `ImportError: cannot import name 'extract_event'`.

- [ ] **Step 4: Implementar en service.py**

En `app/modules/inbox/service.py`, tras `VALID_CATEGORIES`:

```python
VALID_THEMES = ("coach", "formacion", "social", "gimnasio", "padel", "default")

EVENT_PROMPT = (
    "Extrae el evento de esta nota personal. Hoy es {today}.\n"
    "Responde SOLO un JSON: "
    '{{"summary": "<título breve>", "start": "<ISO>", "end": "<ISO>", '
    '"all_day": true|false, "theme": "<tema>"}}.\n'
    "Reglas:\n"
    "- start/end en hora LOCAL ISO sin zona horaria: 'YYYY-MM-DDTHH:MM:SS'.\n"
    "- Si all_day=true, usa solo fecha 'YYYY-MM-DD' y start==end (el día del evento).\n"
    "- Duración explícita ('2h', '90 min') -> end = start + duración.\n"
    "- Inicio y fin dados ('de 18 a 20') -> úsalos tal cual.\n"
    "- Solo hora de inicio -> end = start + 1 hora.\n"
    "- Sin ninguna hora -> all_day=true.\n"
    "- theme: una de [coach, formacion, social, gimnasio, padel]; si no encaja, 'default'.\n\n"
    "Nota:\n{text}"
)


def _parse_event(raw: str) -> dict | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    summary = str(data.get("summary", "")).strip()
    start = str(data.get("start", "")).strip()
    if not (summary and start):
        return None
    end = str(data.get("end", "")).strip() or start
    theme = data.get("theme", "default")
    if theme not in VALID_THEMES:
        theme = "default"
    return {
        "summary": summary,
        "start": start,
        "end": end,
        "all_day": bool(data.get("all_day", False)),
        "theme": theme,
    }


def extract_event(text: str, today: str, llm: Callable[[str], str]) -> dict | None:
    """Returns {summary,start,end,all_day,theme} or None on any failure
    (caller treats None as 'not a usable event' → stays uncertain)."""
    try:
        return _parse_event(llm(EVENT_PROMPT.format(today=today, text=text)))
    except Exception:
        return None
```

- [ ] **Step 5: Run tests, verificar que pasan**

Run: `pytest tests/test_inbox_service.py -k extract_event -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add app/services/llm.py app/modules/inbox/service.py tests/test_inbox_service.py
git commit -m "feat(inbox): extract_event with Sonnet (date/duration/theme)"
```

---

## Task 5: Categoría `event` en clasificación y scan

**Files:**
- Modify: `app/modules/inbox/service.py`
- Test: `tests/test_inbox_service.py`

- [ ] **Step 1: Escribir tests que fallan**

Añade a `tests/test_inbox_service.py`:

```python
def test_classify_event_category():
    llm = lambda p: '{"category":"event","proposed_text":"cena con Marc"}'
    assert classify_note("cena con Marc el viernes 21h", llm)[0] == "event"


def test_scan_event_fills_fields(session, tmp_path):
    _write_note(tmp_path, "2026-06-18-1000-padel.md", NOTE)
    classify = lambda p: '{"category":"event","proposed_text":"pádel"}'
    event_llm = lambda p: '{"summary":"Pádel con Marc","start":"2026-06-20T18:00:00","end":"2026-06-20T19:00:00","all_day":false,"theme":"padel"}'

    item = scan_inbox(session, tmp_path, classify, event_llm=event_llm)[0]

    assert item.category == "event"
    assert item.proposed_text == "Pádel con Marc"
    assert item.event_start == "2026-06-20T18:00:00"
    assert item.theme == "padel"


def test_scan_event_extraction_failure_falls_to_uncertain(session, tmp_path):
    _write_note(tmp_path, "2026-06-18-1000-x.md", NOTE)
    classify = lambda p: '{"category":"event","proposed_text":"algo"}'
    def event_llm(p):
        raise RuntimeError("down")

    item = scan_inbox(session, tmp_path, classify, event_llm=event_llm)[0]

    assert item.category == "uncertain"
    assert item.event_start is None
```

- [ ] **Step 2: Run tests, verificar que fallan**

Run: `pytest tests/test_inbox_service.py -k "event_category or scan_event" -v`
Expected: FAIL — `classify` devuelve `event` pero `VALID_CATEGORIES` no lo incluye → `uncertain`; y `scan_inbox` no acepta `event_llm`.

- [ ] **Step 3: Actualizar VALID_CATEGORIES, CLASSIFY_PROMPT y scan_inbox**

En `app/modules/inbox/service.py`:

Cambia:
```python
VALID_CATEGORIES = ("task", "note", "uncertain")
```
por:
```python
VALID_CATEGORIES = ("task", "note", "event", "uncertain")
```

En `CLASSIFY_PROMPT`, cambia las líneas de categorías y `uncertain` por:
```python
    "- task: algo que hacer sin hora concreta (comprar, llamar, revisar...).\n"
    "- note: información o idea, no accionable.\n"
    "- event: algo con fecha/hora concreta (cita, cena, partido, clase...).\n"
    "- uncertain: ambigua o muy corta.\n"
```
y en la línea del JSON cambia `"task|note|uncertain"` por `"task|note|event|uncertain"`.

Añade un helper para la fecha de hoy (tras los imports / antes de `scan_inbox`):
```python
def _today_str() -> str:
    from zoneinfo import ZoneInfo
    from app.config import settings
    now = datetime.now(ZoneInfo(settings.TIMEZONE))
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    return f"{now:%Y-%m-%d} ({dias[now.weekday()]})"
```

En `scan_inbox`, cambia la firma y el cuerpo del bucle:
```python
def scan_inbox(session: Session, vault_path, llm: Callable[[str], str],
               event_llm: Callable[[str], str] | None = None) -> list[InboxItem]:
    inbox = Path(vault_path) / "inbox"
    if not inbox.exists():
        return []
    seen = {i.filename for i in session.exec(select(InboxItem)).all()}
    created: list[InboxItem] = []
    for path in sorted(inbox.glob("*.md")):
        if path.name in seen:
            continue
        body, source = _read_note(path)
        category, proposed = classify_note(body, llm)
        event_fields = {}
        if category == "event":
            data = extract_event(body, _today_str(), event_llm) if event_llm else None
            if data:
                proposed = data["summary"]
                event_fields = {
                    "event_start": data["start"],
                    "event_end": data["end"],
                    "all_day": data["all_day"],
                    "theme": data["theme"],
                }
            else:
                category = "uncertain"
        item = InboxItem(
            filename=path.name,
            excerpt=body[:200],
            source=source,
            category=category,
            proposed_text=proposed or body[:200],
            status="pending",
            **event_fields,
        )
        session.add(item)
        created.append(item)
    session.commit()
    for item in created:
        session.refresh(item)
    return created
```

- [ ] **Step 4: Run tests, verificar que pasan**

Run: `pytest tests/test_inbox_service.py -k "event_category or scan_event" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run toda la suite del módulo (no regresiones)**

Run: `pytest tests/test_inbox_service.py -v`
Expected: PASS (todos, incluidos los de Fase 1).

- [ ] **Step 6: Commit**

```bash
git add app/modules/inbox/service.py tests/test_inbox_service.py
git commit -m "feat(inbox): event category in classify and scan"
```

---

## Task 6: Acción `apply_event` (crear + archivar + status)

**Files:**
- Modify: `app/modules/inbox/service.py`
- Test: `tests/test_inbox_service.py`

- [ ] **Step 1: Escribir test que falla**

Añade a `tests/test_inbox_service.py` (añade `apply_event` al import):

```python
from app.modules.inbox.service import apply_event  # añadir al bloque de imports


def test_apply_event_creates_archives_and_marks_scheduled(session, tmp_path):
    _write_note(tmp_path, "2026-06-18-1000-padel.md", NOTE)
    classify = lambda p: '{"category":"event","proposed_text":"pádel"}'
    event_llm = lambda p: '{"summary":"Pádel","start":"2026-06-20T18:00:00","end":"2026-06-20T19:00:00","all_day":false,"theme":"padel"}'
    item = scan_inbox(session, tmp_path, classify, event_llm=event_llm)[0]

    calls = {}
    def fake_create(summary, start, end, all_day, theme):
        calls.update(summary=summary, start=start, theme=theme)
        return ("evt123", "https://cal/evt123")

    result, link = apply_event(session, item, tmp_path, fake_create)

    assert calls["summary"] == "Pádel"
    assert calls["theme"] == "padel"
    assert link == "https://cal/evt123"
    assert result.status == "scheduled"
    assert result.calendar_event_id == "evt123"
    assert (tmp_path / "archivo" / "2026-06-18-1000-padel.md").exists()
    assert not (tmp_path / "inbox" / "2026-06-18-1000-padel.md").exists()
```

- [ ] **Step 2: Run test, verificar que falla**

Run: `pytest tests/test_inbox_service.py::test_apply_event_creates_archives_and_marks_scheduled -v`
Expected: FAIL — `ImportError: cannot import name 'apply_event'`.

- [ ] **Step 3: Implementar apply_event**

En `app/modules/inbox/service.py`, tras `apply_item`:

```python
def apply_event(session: Session, item: InboxItem, vault_path,
                create_event: Callable[..., tuple[str, str]]) -> tuple[InboxItem, str]:
    """Crea el evento (create_event inyectado, mockeable), archiva la nota y marca
    el item como scheduled. Devuelve (item, html_link)."""
    vault = Path(vault_path)
    note_path = vault / "inbox" / item.filename
    event_id, link = create_event(
        item.proposed_text, item.event_start, item.event_end, item.all_day, item.theme
    )
    if note_path.exists():
        _move(note_path, vault / "archivo")
    item.status = "scheduled"
    item.calendar_event_id = event_id
    item.resolved_at = datetime.utcnow()
    session.add(item)
    session.commit()
    session.refresh(item)
    return item, link
```

- [ ] **Step 4: Run test, verificar que pasa**

Run: `pytest tests/test_inbox_service.py::test_apply_event_creates_archives_and_marks_scheduled -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/modules/inbox/service.py tests/test_inbox_service.py
git commit -m "feat(inbox): apply_event creates calendar event and archives note"
```

---

## Task 7: Tarjeta de evento en el digest

**Files:**
- Modify: `bot/inbox_handlers.py`
- Test: `tests/test_inbox_handlers.py`

- [ ] **Step 1: Escribir test que falla**

Añade a `tests/test_inbox_handlers.py`:

```python
def test_build_digest_event_card(session, tmp_path):
    _write(tmp_path, "ev.md")
    classify = lambda p: '{"category":"event","proposed_text":"x"}'
    event_llm = lambda p: '{"summary":"Pádel con Marc","start":"2026-06-20T18:00:00","end":"2026-06-20T19:00:00","all_day":false,"theme":"padel"}'
    scan_inbox(session, tmp_path, classify, event_llm=event_llm)

    messages = ih.build_digest(session)

    assert len(messages) == 1
    text, kb = messages[0]
    assert "Pádel con Marc" in text
    assert "padel" in text
    datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert any(d.startswith("inbox:event:") for d in datas)
    assert any(d.startswith("inbox:editdate:") for d in datas)
```

- [ ] **Step 2: Run test, verificar que falla**

Run: `pytest tests/test_inbox_handlers.py::test_build_digest_event_card -v`
Expected: FAIL — no hay tarjeta de evento; `len(messages)` no es 1 / faltan callbacks.

- [ ] **Step 3: Implementar tarjeta de evento en build_digest**

En `bot/inbox_handlers.py`, añade un helper antes de `build_digest`:

```python
def _fmt_when(item) -> str:
    from datetime import datetime
    if item.all_day:
        return f"{item.event_start} (todo el día)"
    try:
        s = datetime.fromisoformat(item.event_start)
        e = datetime.fromisoformat(item.event_end)
        return f"{s:%d/%m %H:%M}–{e:%H:%M}"
    except (ValueError, TypeError):
        return item.event_start or ""


def _event_card(item) -> tuple[str, InlineKeyboardMarkup]:
    text = f"📅 *Evento*: {item.proposed_text}  [{item.theme}]\n{_fmt_when(item)}"
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Crear", callback_data=f"inbox:event:{item.id}"),
            InlineKeyboardButton("✏️ Editar fecha", callback_data=f"inbox:editdate:{item.id}"),
        ],
        [
            InlineKeyboardButton("📄 Archivar", callback_data=f"inbox:note:{item.id}"),
            InlineKeyboardButton("✗ Descartar", callback_data=f"inbox:discard:{item.id}"),
        ],
    ])
    return text, kb
```

En `build_digest`, el lote de confiables debe excluir `event`, y hay que emitir una tarjeta por evento. Cambia la línea:
```python
    confident = [i for i in items if i.category in ("task", "note")]
```
(se queda igual: `event` ya no entra en el lote). Y antes del `return messages`, añade el bucle de eventos:
```python
    for i in items:
        if i.category == "event":
            messages.append(_event_card(i))
```

- [ ] **Step 4: Run test, verificar que pasa**

Run: `pytest tests/test_inbox_handlers.py::test_build_digest_event_card -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bot/inbox_handlers.py tests/test_inbox_handlers.py
git commit -m "feat(inbox): event card in telegram digest"
```

---

## Task 8: Callbacks `event` y `editdate` + re-extracción

**Files:**
- Modify: `bot/inbox_handlers.py`
- Modify: `bot/handlers.py:380-384`
- Test: `tests/test_inbox_handlers.py`

- [ ] **Step 1: Escribir tests que fallan**

Añade a `tests/test_inbox_handlers.py`:

```python
async def test_callback_event_creates_and_replies_link(monkeypatch, tmp_path, session):
    monkeypatch.setattr(ih.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    _write(tmp_path, "ev.md")
    classify = lambda p: '{"category":"event","proposed_text":"x"}'
    event_llm = lambda p: '{"summary":"Pádel","start":"2026-06-20T18:00:00","end":"2026-06-20T19:00:00","all_day":false,"theme":"padel"}'
    item = scan_inbox(session, tmp_path, classify, event_llm=event_llm)[0]
    monkeypatch.setattr(ih, "cal_create_event", lambda *a, **k: ("evt1", "https://cal/evt1"))

    update, query = make_callback_update(f"inbox:event:{item.id}")
    await ih.callback_inbox(update, make_context())

    assert "https://cal/evt1" in query.edit_message_text.call_args.args[0]
    assert (tmp_path / "archivo" / "ev.md").exists()


async def test_callback_editdate_prompts_and_sets_state(monkeypatch, tmp_path, session):
    monkeypatch.setattr(ih.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    _write(tmp_path, "ev.md")
    classify = lambda p: '{"category":"event","proposed_text":"x"}'
    event_llm = lambda p: '{"summary":"Pádel","start":"2026-06-20T18:00:00","end":"2026-06-20T19:00:00","all_day":false,"theme":"padel"}'
    item = scan_inbox(session, tmp_path, classify, event_llm=event_llm)[0]

    update, query = make_callback_update(f"inbox:editdate:{item.id}")
    context = make_context()
    await ih.callback_inbox(update, context)

    assert context.user_data["inbox_event_edit_id"] == item.id
    assert "fecha" in query.edit_message_text.call_args.args[0].lower()


async def test_reextract_event_date_updates_and_resends_card(monkeypatch, tmp_path, session):
    monkeypatch.setattr(ih.settings, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    _write(tmp_path, "ev.md")
    classify = lambda p: '{"category":"event","proposed_text":"x"}'
    event_llm = lambda p: '{"summary":"Pádel","start":"2026-06-20T18:00:00","end":"2026-06-20T19:00:00","all_day":false,"theme":"padel"}'
    item = scan_inbox(session, tmp_path, classify, event_llm=event_llm)[0]
    monkeypatch.setattr(ih, "complete_event",
                        lambda p: '{"summary":"Pádel","start":"2026-06-21T10:00:00","end":"2026-06-21T11:00:00","all_day":false,"theme":"padel"}')

    update = make_update()
    update.effective_chat.send_message = AsyncMock()
    handled = await ih.reextract_event_date(update, item.id, "mejor el sábado a las 10")

    assert handled is True
    sent = update.effective_chat.send_message.call_args
    assert "21/06 10:00" in sent.kwargs.get("text", sent.args[0] if sent.args else "")
```

- [ ] **Step 2: Run tests, verificar que fallan**

Run: `pytest tests/test_inbox_handlers.py -k "event_creates or editdate or reextract" -v`
Expected: FAIL — faltan `cal_create_event`, ramas de callback y `reextract_event_date`.

- [ ] **Step 3: Implementar en bot/inbox_handlers.py**

Actualiza los imports al inicio del archivo:
```python
from app.services.llm import complete_tags, complete_event
from app.services.calendar import create_event as cal_create_event
from app.modules.inbox.service import (
    scan_inbox, pending_items, apply_item, apply_suggested, get_item, apply_event,
    extract_event, _today_str,
)
```

En `_scan_and_digest`, pasa el extractor de eventos:
```python
def _scan_and_digest(vault_path) -> list[tuple[str, InlineKeyboardMarkup | None]]:
    with Session(engine) as session:
        scan_inbox(session, vault_path, complete_tags, event_llm=complete_event)
        return build_digest(session)
```

En `callback_inbox`, tras el bloque `if action == "edit":`, añade las ramas nuevas (antes del `with Session(engine) as session:` que aplica task/note/discard):
```python
    if action == "editdate":
        context.user_data["inbox_event_edit_id"] = item_id
        await _edit_or_send(update, query, "Envíame la fecha corregida del evento.")
        return

    if action == "event":
        with Session(engine) as session:
            item = get_item(session, item_id)
            if not item or item.status != "pending":
                await _edit_or_send(update, query, "Ya resuelta.")
                return
            _, link = apply_event(session, item, settings.OBSIDIAN_VAULT_PATH, cal_create_event)
        await _edit_or_send(update, query, f"📅 Evento creado: {link}")
        return
```

Añade la función de re-extracción al final del archivo:
```python
async def reextract_event_date(update: Update, item_id: int, text: str) -> bool:
    """Re-extrae fecha/hora del evento con el texto corregido y reenvía la tarjeta
    para confirmar (no crea el evento). False si el item ya no está pending."""
    with Session(engine) as session:
        item = get_item(session, item_id)
        if not item or item.status != "pending":
            return False
        data = extract_event(text, _today_str(), complete_event)
        if not data:
            await safe_reply(update, "No pude entender la fecha. Prueba de nuevo o usa los botones.")
            return True
        item.proposed_text = data["summary"]
        item.event_start = data["start"]
        item.event_end = data["end"]
        item.all_day = data["all_day"]
        item.theme = data["theme"]
        session.add(item)
        session.commit()
        session.refresh(item)
        card_text, kb = _event_card(item)
    await update.effective_chat.send_message(text=card_text, parse_mode="Markdown", reply_markup=kb)
    return True
```

- [ ] **Step 4: Enganchar el texto en bot/handlers.py**

En `bot/handlers.py`, dentro de `message`, tras el bloque de `inbox_edit_id` (línea ~384), añade:
```python
    event_edit_id = context.user_data.pop("inbox_event_edit_id", None)
    if event_edit_id is not None:
        from bot.inbox_handlers import reextract_event_date
        if await reextract_event_date(update, event_edit_id, update.message.text.strip()):
            return
```

- [ ] **Step 5: Run tests, verificar que pasan**

Run: `pytest tests/test_inbox_handlers.py -k "event_creates or editdate or reextract" -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Run toda la suite del bot (no regresiones)**

Run: `pytest tests/test_inbox_handlers.py tests/test_bot_handlers.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add bot/inbox_handlers.py bot/handlers.py tests/test_inbox_handlers.py
git commit -m "feat(inbox): event create/editdate callbacks and date re-extraction"
```

---

## Task 9: Script OAuth one-time

**Files:**
- Create: `scripts/google_auth.py`

- [ ] **Step 1: Crear scripts/google_auth.py**

```python
"""OAuth one-time para Google Calendar. Corre UNA vez en local (abre navegador):
    python scripts/google_auth.py
Requiere GOOGLE_CALENDAR_CREDENTIALS (client secret de un OAuth Client tipo Desktop,
Calendar API habilitada). Guarda el token en GOOGLE_CALENDAR_TOKEN.
En prod: copia el token generado al volumen /srv/surehub/data del contenedor bot."""
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from app.config import settings
from app.services.calendar import SCOPES


def main() -> None:
    flow = InstalledAppFlow.from_client_secrets_file(
        settings.GOOGLE_CALENDAR_CREDENTIALS, SCOPES
    )
    creds = flow.run_local_server(port=0)
    Path(settings.GOOGLE_CALENDAR_TOKEN).write_text(creds.to_json(), encoding="utf-8")
    print(f"Token guardado en {settings.GOOGLE_CALENDAR_TOKEN}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verificar que importa (sin correr el flujo)**

Run: `python -c "import scripts.google_auth"`
Expected: sin error (no abre navegador; solo importa).

- [ ] **Step 3: Commit**

```bash
git add scripts/google_auth.py
git commit -m "feat(inbox): one-time google calendar oauth script"
```

---

## Task 10: Documentación

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/architecture.md`
- Modify: `docs/BACKLOG.md`

- [ ] **Step 1: Actualizar CLAUDE.md — sección Inbox**

En la sección "Estado actual del módulo Inbox (Obsidian)":
- Cambia la línea de clasificación a incluir `event`: `task | note | event | uncertain`.
- Añade bullet: "Eventos (`event`): Sonnet extrae fecha/duración/temática (`extract_event`), tarjeta individual en el digest, `📅 Crear` → Google Calendar con color por temática (`CALENDAR_COLORS`), nota → `archivo/`, status `scheduled`, responde con link. Editar fecha re-extrae."
- Cambia la línea "Fase 2 pendiente: eventos → Google Calendar (OAuth)" por: "Fase 2 (hecho 2026-06-18): eventos → Google Calendar (OAuth one-time vía `scripts/google_auth.py`). Spec: `docs/superpowers/specs/2026-06-18-inbox-calendar-events-design.md`."

En la sección "Bot Telegram", añade a "Consultas y acciones" o cerca del inbox una nota de que los eventos no tienen comando (se gestionan desde el digest).

Añade a las env vars documentadas (si hay lista) o deja que `.env.example` lo cubra: `GOOGLE_CALENDAR_CREDENTIALS`, `GOOGLE_CALENDAR_TOKEN`, `GOOGLE_CALENDAR_ID`.

- [ ] **Step 2: Actualizar docs/architecture.md**

Añade el servicio `app/services/calendar.py` al mapa de componentes (wrapper Google Calendar, `CALENDAR_COLORS`, OAuth token en volumen) y menciona la 2ª llamada LLM (Sonnet) para extracción de eventos en el flujo de inbox.

- [ ] **Step 3: Actualizar docs/BACKLOG.md**

Mueve la línea de "Inbox Fase 2" de "Pendiente" a "Hecho":
```markdown
- [x] **Inbox Fase 2** (2026-06-18) — eventos con fecha/hora → Google Calendar (OAuth
  one-time). Categoría `event`, extracción Sonnet, color por temática, tarjeta individual.
  Spec: `docs/superpowers/specs/2026-06-18-inbox-calendar-events-design.md`.
```
Deja "Pendiente" sin esa línea (queda `(vacío)` o el resto).

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/architecture.md docs/BACKLOG.md
git commit -m "docs: inbox phase 2 events to google calendar"
```

---

## Task 11: Suite completa y cierre

- [ ] **Step 1: Run toda la suite**

Run: `pytest -q`
Expected: PASS (incluye los tests nuevos de calendar, service y handlers; sin regresiones en Fase 1).

- [ ] **Step 2: Push (dispara CI → deploy)**

```bash
git push origin main
```

- [ ] **Step 3: Setup manual en prod (checklist, fuera del código)**

1. Crear OAuth Client (Desktop) en Google Cloud Console, habilitar Calendar API, descargar client secret.
2. En local: `python scripts/google_auth.py` → genera `google_token.json`.
3. Copiar client secret + token al volumen `/srv/surehub/data` del server.
4. Setear `GOOGLE_CALENDAR_*` en el `.env` de prod (rutas dentro del volumen).
5. Aplicar el `ALTER TABLE` de Task 2 sobre `/srv/surehub/data/surehub.db`.
6. Reiniciar el contenedor `bot`.
7. Documentar en repo `SureKT/homelab` → `docs/surehub.md` (montaje de token + migración).

---

## Self-Review (cubierto)

- **Spec coverage:** categoría `event` (T5), extracción Sonnet duración/inicio-fin/all-day/temática (T4), servicio Calendar + color (T3), campos modelo (T2), tarjeta individual + editar fecha (T7,T8), OAuth one-time (T9), config + deps (T1), reversibilidad vía link (T8), docs + deploy (T10,T11). Todo del spec tiene tarea.
- **Type consistency:** `extract_event(text, today, llm) -> dict|None`; `apply_event(session,item,vault,create_event) -> (item, link)`; `create_event(summary,start,end,all_day,theme) -> (id, link)`; `cal_create_event` alias en handlers; `_event_card`/`_fmt_when` reusados por digest y re-extracción. Coherente entre tareas.
- **No placeholders:** todos los steps con código real y comandos con expected.
</content>
