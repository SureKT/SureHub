from sqlmodel import select

from app.modules.inbox.models import InboxItem
from app.modules.inbox.service import classify_note


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
