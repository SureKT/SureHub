from app.modules.memoria.service import (
    build_context,
    delete_memory,
    list_memories,
    save_memory,
    update_memory,
)


def test_save_memory(session):
    m = save_memory(session, "le gusta el pádel")
    assert m.id is not None
    assert m.fact == "le gusta el pádel"
    assert m.date is not None


def test_list_memories_ordered_by_date(session):
    save_memory(session, "primero")
    save_memory(session, "segundo")
    facts = [m.fact for m in list_memories(session)]
    assert facts == ["primero", "segundo"]


def test_update_memory(session):
    m = save_memory(session, "original")
    updated = update_memory(session, m.id, "corregido")
    assert updated.fact == "corregido"
    assert list_memories(session)[0].fact == "corregido"


def test_update_missing_returns_none(session):
    assert update_memory(session, 999, "nada") is None


def test_delete_memory(session):
    m = save_memory(session, "borrable")
    assert delete_memory(session, m.id) is True
    assert list_memories(session) == []


def test_delete_missing_returns_false(session):
    assert delete_memory(session, 999) is False


def test_build_context_empty(session):
    assert build_context(session) == ""


def test_build_context_format(session):
    save_memory(session, "le gusta el pádel")
    save_memory(session, "vive en Valencia")
    context = build_context(session)
    assert context.startswith("Lo que sabes del usuario:")
    assert "- le gusta el pádel" in context
    assert "- vive en Valencia" in context
