import pytest

from app.modules.notes.service import create_note, extract_tags, generate_tags


def llm_ok(prompt: str) -> str:
    return '["ideas", "App", "ideas"]'


def llm_fail(prompt: str) -> str:
    raise RuntimeError("API down")


def test_create_note_with_tags(tmp_path):
    path = create_note("idea para una app de notas", tmp_path, llm_ok)

    assert path.exists()
    assert path.parent == tmp_path / "inbox"
    content = path.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    assert "created: " in content
    assert "tags: [ideas, app]" in content
    assert "source: telegram" in content
    assert content.rstrip().endswith("idea para una app de notas")
    assert extract_tags(path) == ["ideas", "app"]


def test_short_note_skips_llm(tmp_path):
    called = []

    def spy(prompt: str) -> str:
        called.append(prompt)
        return '["x"]'

    path = create_note("hola mundo", tmp_path, spy)
    assert path.exists()
    assert called == []
    assert "tags: []" in path.read_text(encoding="utf-8")


def test_llm_failure_still_writes_note(tmp_path):
    path = create_note("nota que no debe perderse", tmp_path, llm_fail)

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "tags: []" in content
    assert "nota que no debe perderse" in content
    assert extract_tags(path) == []


def test_filename_collision_gets_suffix(tmp_path):
    first = create_note("misma nota", tmp_path, llm_ok)
    second = create_note("misma nota", tmp_path, llm_ok)
    third = create_note("misma nota", tmp_path, llm_ok)

    assert first != second != third
    assert second.stem == f"{first.stem}-2"
    assert third.stem == f"{first.stem}-3"
    assert all(p.exists() for p in (first, second, third))


def test_missing_vault_path_is_created(tmp_path):
    vault = tmp_path / "no" / "existe" / "vault"
    assert not vault.exists()

    path = create_note("nota en vault nuevo", vault, llm_ok)

    assert path.exists()
    assert path.parent == vault / "inbox"


def test_filename_slug_from_first_words(tmp_path):
    path = create_note("Comprar café para la oficina mañana sin falta", tmp_path, llm_ok)
    assert path.name.endswith("-comprar-cafe-para-la-oficina.md")


def test_create_note_uses_explicit_timezone(tmp_path):
    # Tokyo no tiene DST → offset siempre +09:00, test estable independiente de la fecha.
    path = create_note("nota con zona horaria explicita", tmp_path, llm_ok, tz="Asia/Tokyo")
    created = next(l for l in path.read_text(encoding="utf-8").splitlines() if l.startswith("created:"))
    assert "+09:00" in created


def test_create_note_default_timezone_is_madrid(tmp_path):
    path = create_note("otra nota con zona por defecto", tmp_path, llm_ok)
    created = next(l for l in path.read_text(encoding="utf-8").splitlines() if l.startswith("created:"))
    # Europe/Madrid: +01:00 (invierno) o +02:00 (verano), nunca UTC.
    assert "+01:00" in created or "+02:00" in created


@pytest.mark.parametrize("raw,expected", [
    ('["ideas", "trabajo"]', ["ideas", "trabajo"]),
    ('Aquí tienes: ["casa", "compras"]', ["casa", "compras"]),
    ("ideas, trabajo, app", ["ideas", "trabajo", "app"]),
    ("#Ideas, #Trabajo", ["ideas", "trabajo"]),
    ('["a", "b", "c", "d", "e", "f", "g"]', ["a", "b", "c", "d", "e"]),
])
def test_generate_tags_tolerant_parsing(raw, expected):
    assert generate_tags("nota con suficiente texto", lambda prompt: raw) == expected
