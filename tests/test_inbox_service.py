from sqlmodel import select

from app.modules.inbox.models import InboxItem
from app.modules.inbox.service import (
    classify_note,
    scan_inbox,
    apply_item,
    apply_suggested,
    pending_items,
    get_item,
    extract_event,
    apply_event,
)


def test_inbox_item_persists(session):
    item = InboxItem(filename="2026-06-18-1000-x.md", category="task", proposed_text="comprar pan")
    session.add(item)
    session.commit()

    rows = session.exec(select(InboxItem)).all()
    assert len(rows) == 1
    assert rows[0].status == "pending"
    assert rows[0].filename == "2026-06-18-1000-x.md"


def test_classify_task():
    llm = lambda prompt: '{"category": "task", "proposed_text": "comprar pan"}'
    assert classify_note("tengo que comprar pan", llm) == ("task", "comprar pan")


def test_classify_note_category():
    llm = lambda prompt: 'Claro: {"category": "note", "proposed_text": "idea sobre x"}'
    assert classify_note("una idea sobre x", llm) == ("note", "idea sobre x")


def test_classify_invalid_category_becomes_uncertain():
    llm = lambda prompt: '{"category": "evento", "proposed_text": "cena jueves"}'
    cat, _ = classify_note("cena el jueves", llm)
    assert cat == "uncertain"


def test_classify_llm_failure_is_uncertain():
    def llm(prompt):
        raise RuntimeError("API down")
    cat, text = classify_note("nota cualquiera", llm)
    assert cat == "uncertain"
    assert text == "nota cualquiera"


def test_classify_non_json_is_uncertain():
    llm = lambda prompt: "no soy json"
    assert classify_note("algo", llm)[0] == "uncertain"


NOTE = """---
created: 2026-06-18T10:00:00+02:00
tags: [compras]
source: telegram-voice
---

tengo que comprar pan y leche
"""


def _write_note(vault, name, content=NOTE):
    inbox = vault / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / name).write_text(content, encoding="utf-8")


def test_scan_creates_items_for_new_notes(session, tmp_path):
    _write_note(tmp_path, "2026-06-18-1000-pan.md")
    llm = lambda prompt: '{"category": "task", "proposed_text": "comprar pan y leche"}'

    created = scan_inbox(session, tmp_path, llm)

    assert len(created) == 1
    item = created[0]
    assert item.filename == "2026-06-18-1000-pan.md"
    assert item.category == "task"
    assert item.proposed_text == "comprar pan y leche"
    assert item.source == "telegram-voice"
    assert item.status == "pending"


def test_scan_skips_already_seen(session, tmp_path):
    _write_note(tmp_path, "2026-06-18-1000-pan.md")
    llm = lambda prompt: '{"category": "task", "proposed_text": "x"}'

    scan_inbox(session, tmp_path, llm)
    created_again = scan_inbox(session, tmp_path, llm)

    assert created_again == []


def test_scan_no_inbox_dir_returns_empty(session, tmp_path):
    assert scan_inbox(session, tmp_path, lambda p: "{}") == []


def test_apply_task_appends_and_archives(session, tmp_path):
    _write_note(tmp_path, "2026-06-18-1000-pan.md")
    llm = lambda prompt: '{"category": "task", "proposed_text": "comprar pan"}'
    item = scan_inbox(session, tmp_path, llm)[0]

    apply_item(session, item, tmp_path, "task")

    tasks = (tmp_path / "Tareas.md").read_text(encoding="utf-8")
    assert "- [ ] comprar pan" in tasks
    assert "[[2026-06-18-1000-pan]]" in tasks
    assert not (tmp_path / "inbox" / "2026-06-18-1000-pan.md").exists()
    assert (tmp_path / "archivo" / "2026-06-18-1000-pan.md").exists()
    assert item.status == "approved"


def test_apply_task_override_text(session, tmp_path):
    _write_note(tmp_path, "n.md")
    item = scan_inbox(session, tmp_path, lambda p: '{"category":"task","proposed_text":"mal"}')[0]

    apply_item(session, item, tmp_path, "task", override_text="texto corregido")

    assert "- [ ] texto corregido" in (tmp_path / "Tareas.md").read_text(encoding="utf-8")


def test_apply_note_archives(session, tmp_path):
    _write_note(tmp_path, "n.md")
    item = scan_inbox(session, tmp_path, lambda p: '{"category":"note","proposed_text":"idea"}')[0]

    apply_item(session, item, tmp_path, "note")

    assert (tmp_path / "archivo" / "n.md").exists()
    assert not (tmp_path / "Tareas.md").exists()
    assert item.status == "archived"


def test_apply_discard_moves_to_descartado(session, tmp_path):
    _write_note(tmp_path, "n.md")
    item = scan_inbox(session, tmp_path, lambda p: '{"category":"uncertain","proposed_text":"?"}')[0]

    apply_item(session, item, tmp_path, "discard")

    assert (tmp_path / "inbox" / "_descartado" / "n.md").exists()
    assert item.status == "discarded"


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
    assert data["end"] == "2026-06-25"


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


def test_apply_suggested_applies_task_and_note_only(session, tmp_path):
    _write_note(tmp_path, "a.md")
    _write_note(tmp_path, "b.md")
    _write_note(tmp_path, "c.md")
    cats = iter([
        '{"category":"task","proposed_text":"t"}',
        '{"category":"note","proposed_text":"n"}',
        '{"category":"uncertain","proposed_text":"?"}',
    ])
    scan_inbox(session, tmp_path, lambda p: next(cats))

    counts = apply_suggested(session, tmp_path)

    assert counts == {"task": 1, "note": 1}
    # the uncertain one stays pending
    assert len(pending_items(session)) == 1
    assert pending_items(session)[0].category == "uncertain"
