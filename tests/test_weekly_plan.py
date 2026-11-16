import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.modules.routines import weekly_plan as wp
from app.modules.routines.engines import EngineResult
from app.modules.routines.registry import ROUTINES
from app.modules.routines.service import execute, load_json
from app.services import calendar as calendar_api

TZ = ZoneInfo("Europe/Madrid")
MON, SUN = date(2026, 11, 23), date(2026, 11, 29)

PADEL = {"id": "e1", "summary": "Pádel", "start": "2026-11-23T20:30:00",
         "end": "2026-11-23T22:00:00", "all_day": False, "surehub_run": None}
BDAY = {"id": "e2", "summary": "Cumple", "start": "2026-11-24", "end": "2026-11-25",
        "all_day": True, "surehub_run": None}


def _block(title, start, end, theme="formacion"):
    return {"title": title, "start": start, "end": end, "theme": theme}


def _model(blocks, summary="Semana de foco en la app"):
    return json.dumps({"summary": summary, "blocks": blocks}, ensure_ascii=False)


# ── window ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("now,expected", [
    (datetime(2026, 11, 22, 19, tzinfo=TZ), (MON, SUN, "2026-W48")),          # scheduled Sunday
    (datetime(2026, 11, 23, 8, tzinfo=TZ), (MON, SUN, "2026-W48")),           # Monday catch-up
    (datetime(2026, 11, 25, 15, tzinfo=TZ), (date(2026, 11, 26), SUN, "2026-W48")),  # mid-week manual
    (datetime(2026, 12, 27, 19, tzinfo=TZ), (date(2026, 12, 28), date(2027, 1, 3), "2026-W53")),
])
def test_plan_window(now, expected):
    assert wp.plan_window(now) == expected


# ── vault inputs ────────────────────────────────────────────────────────────

def _vault(tmp_path):
    (tmp_path / "planificacion" / "revisiones").mkdir(parents=True)
    (tmp_path / "Tareas.md").write_text("- [x] hecho\n- [ ] Actualizar DNI\n\ttexto suelto\n- [ ] Pihole\n",
                                        encoding="utf-8")
    (tmp_path / "planificacion" / "plan-activo.md").write_text(
        "---\ntipo: plan\nestado: activo\n---\n# Plan\nproyecto 9-12", encoding="utf-8")
    (tmp_path / "planificacion" / "plan-viejo.md").write_text(
        "---\nestado: cerrado\n---\nviejo", encoding="utf-8")
    (tmp_path / "planificacion" / "revisiones" / "2026-11-15.md").write_text("antigua", encoding="utf-8")
    (tmp_path / "planificacion" / "revisiones" / "2026-11-22.md").write_text("reciente", encoding="utf-8")
    (tmp_path / "planificacion" / "plan-activo.sync-conflict-20261101-1-ABC.md").write_text(
        "---\nestado: activo\n---\nconflicto", encoding="utf-8")
    return tmp_path


def test_read_inputs_filters_modes_and_syncthing_files(tmp_path):
    inputs = {rel: content for _, rel, content in wp.read_inputs(_vault(tmp_path))}

    assert inputs["Tareas.md"] == "- [ ] Actualizar DNI\n- [ ] Pihole"
    assert "proyecto 9-12" in inputs["planificacion/plan-activo.md"]
    assert "planificacion/plan-viejo.md" not in inputs
    assert list(k for k in inputs if "revisiones" in k) == ["planificacion/revisiones/2026-11-22.md"]
    assert not any("sync-conflict" in k for k in inputs)


def test_is_ignored(tmp_path):
    for rel in (".stversions/a.md", ".obsidian/app.json", "x/.syncthing.a.md.tmp", "a.sync-conflict-1-X.md"):
        assert wp.is_ignored(tmp_path / rel, tmp_path)
    assert not wp.is_ignored(tmp_path / "planificacion" / "a.md", tmp_path)


def test_revision_freshness(tmp_path):
    vault = _vault(tmp_path)
    assert wp.revision_is_fresh(vault, MON) is True
    assert wp.revision_is_fresh(vault, date(2026, 12, 7)) is False
    assert wp.revision_is_fresh(tmp_path / "nope", MON) is False


# ── parsing / validation ────────────────────────────────────────────────────

def test_parse_proposal_validates_in_code():
    text = "Aquí va:\n" + _model([
        _block("App pádel", "2026-11-23T09:00", "2026-11-23T12:00"),
        _block("Solapa pádel", "2026-11-23T21:00", "2026-11-23T22:00", "padel"),
        _block("Fuera", "2026-11-30T09:00", "2026-11-30T10:00"),
        _block("Al revés", "2026-11-24T12:00", "2026-11-24T11:00"),
        _block("Choca consigo", "2026-11-23T11:00", "2026-11-23T13:00"),
        _block("Tema raro", "2026-11-24T10:00", "2026-11-24T11:00", "inventado"),
        {"title": "sin fechas"},
    ])
    p = wp.parse_proposal(text, MON, SUN, [PADEL, BDAY])

    assert [b["title"] for b in p["blocks"]] == ["App pádel", "Tema raro"]
    assert p["blocks"][0]["start"] == "2026-11-23T09:00:00"   # normalized with seconds
    assert p["blocks"][1]["theme"] == "default"
    reasons = {d["title"]: d["reason"] for d in p["dropped"]}
    assert reasons["Solapa pádel"] == "se solapa con un evento existente"
    assert reasons["Fuera"] == "fuera de la semana"
    assert reasons["Al revés"] == "duración inválida"
    assert reasons["Choca consigo"] == "se solapa con un evento existente"
    assert reasons["sin fechas"] == "formato inválido"


def test_all_day_events_do_not_block_slots():
    p = wp.parse_proposal(_model([_block("Trabajo", "2026-11-24T09:00", "2026-11-24T12:00")]),
                          MON, SUN, [BDAY])
    assert len(p["blocks"]) == 1


def test_parse_proposal_without_json_raises():
    with pytest.raises(ValueError):
        wp.parse_proposal("lo siento, no puedo", MON, SUN, [])


def test_build_prompt_includes_events_inputs_themes_and_correction():
    events = [PADEL, {**BDAY, "surehub_run": "3"}]
    prompt = wp.build_prompt(MON, SUN, "2026-W48", [("Tareas", "Tareas.md", "- [ ] DNI")], events,
                             previous={"summary": "s", "blocks": [{"title": "X"}]},
                             correction="mueve el gimnasio al jueves")
    assert "2026-11-23T20:30 → 22:00: Pádel" in prompt
    assert "[creado por SureHub]" in prompt
    assert "- [ ] DNI" in prompt
    assert "padel:" in prompt and "default:" in prompt
    assert "mueve el gimnasio al jueves" in prompt
    assert '"title": "X"' in prompt


# ── run() through the generic executor ──────────────────────────────────────

@pytest.fixture
def fake_world(monkeypatch, tmp_path):
    vault = _vault(tmp_path)
    monkeypatch.setattr(wp.settings, "OBSIDIAN_VAULT_PATH", str(vault))
    monkeypatch.setattr(calendar_api, "list_events", lambda s, e: [PADEL])
    prompts = []

    def engine(name, prompt, **kw):
        prompts.append(prompt)
        return EngineResult(text=_model([_block("App pádel", "2026-11-23T09:00", "2026-11-23T12:00"),
                                         _block("Gimnasio", "2026-11-24T08:00", "2026-11-24T09:00",
                                                "gimnasio")]),
                            cost_usd=0.02)

    monkeypatch.setattr(wp, "run_engine", engine)
    return {"vault": vault, "prompts": prompts}


def test_run_produces_pending_proposal(session, fake_world):
    run = execute(session, ROUTINES["weekly_plan"], "scheduled",
                  now=datetime(2026, 11, 22, 19, tzinfo=TZ))

    assert run.status == "awaiting_approval"
    assert run.cost_usd == 0.02
    out = load_json(run.output)
    assert out["week"] == "2026-W48"
    assert len(out["blocks"]) == 2
    assert out["events_considered"] == 1
    assert out["warnings"] == []   # 2026-11-22 revision is fresh


def test_run_without_calendar_fails(session, fake_world, monkeypatch):
    def down(s, e):
        raise ValueError("Google Calendar no conectado")
    monkeypatch.setattr(calendar_api, "list_events", down)
    run = execute(session, ROUTINES["weekly_plan"], "scheduled")
    assert run.status == "failed"
    assert "no conectado" in run.error


def test_run_with_no_valid_blocks_fails(session, fake_world, monkeypatch):
    monkeypatch.setattr(wp, "run_engine", lambda *a, **k: EngineResult(text=_model([])))
    run = execute(session, ROUTINES["weekly_plan"], "manual")
    assert run.status == "failed"


def test_adjust_keeps_week_and_sends_correction(session, fake_world):
    parent = execute(session, ROUTINES["weekly_plan"], "scheduled",
                     now=datetime(2026, 11, 22, 19, tzinfo=TZ))
    # correction arrives Monday afternoon: still week 48, not "from tomorrow"
    child = execute(session, ROUTINES["weekly_plan"], "adjust", parent=parent,
                    correction="sin gimnasio el martes", now=datetime(2026, 11, 23, 16, tzinfo=TZ))

    assert load_json(child.output)["start"] == "2026-11-23"
    assert load_json(child.output)["correction"] == "sin gimnasio el martes"
    assert "sin gimnasio el martes" in fake_world["prompts"][-1]


# ── approve / undo ──────────────────────────────────────────────────────────

def test_approve_creates_colored_tagged_events_and_note(session, fake_world, monkeypatch):
    run = execute(session, ROUTINES["weekly_plan"], "scheduled",
                  now=datetime(2026, 11, 22, 19, tzinfo=TZ))
    calls = []
    monkeypatch.setattr(calendar_api, "create_event",
                        lambda *a, **k: calls.append((a, k)) or (f"ev{len(calls)}", "link"))

    result = wp.approve(session, run, fake_world["vault"])

    assert run.status == "approved"
    assert result["created"] == {"0": "ev1", "1": "ev2"}
    (title, start, end, all_day, theme), kw = calls[1]
    assert (title, theme, all_day) == ("Gimnasio", "gimnasio", False)
    assert kw["private"] == {"surehub_run": run.id, "surehub_routine": "weekly_plan"}

    note = fake_world["vault"] / "_surehub" / "planificacion" / "2026-W48.md"
    text = note.read_text(encoding="utf-8")
    assert "semana: 2026-W48" in text and "08:00–09:00 · Gimnasio `gimnasio`" in text
    assert not list(note.parent.glob(".syncthing.*"))   # atomic write leaves no temp


def test_approve_retry_after_partial_failure_does_not_duplicate(session, fake_world, monkeypatch):
    run = execute(session, ROUTINES["weekly_plan"], "manual",
                  now=datetime(2026, 11, 22, 19, tzinfo=TZ))
    calls = []

    def flaky(*a, **k):
        calls.append(a[0])
        if len(calls) == 2:
            raise RuntimeError("Google 500")
        return f"ev{len(calls)}", "link"

    monkeypatch.setattr(calendar_api, "create_event", flaky)
    with pytest.raises(RuntimeError):
        wp.approve(session, run, fake_world["vault"])
    assert load_json(run.result)["created"] == {"0": "ev1"}
    assert run.status == "approving"

    wp.approve(session, run, fake_world["vault"])
    assert calls == ["App pádel", "Gimnasio", "Gimnasio"]   # first block never recreated
    assert run.status == "approved"


def test_undo_deletes_events_and_note(session, fake_world, monkeypatch):
    run = execute(session, ROUTINES["weekly_plan"], "manual",
                  now=datetime(2026, 11, 22, 19, tzinfo=TZ))
    monkeypatch.setattr(calendar_api, "create_event", lambda *a, **k: (f"id-{a[0]}", "l"))
    wp.approve(session, run, fake_world["vault"])
    deleted = []
    monkeypatch.setattr(calendar_api, "delete_event", deleted.append)

    n = wp.undo(session, run, fake_world["vault"])

    assert n == 2 and sorted(deleted) == ["id-App pádel", "id-Gimnasio"]
    assert run.status == "undone"
    assert not (fake_world["vault"] / "_surehub" / "planificacion" / "2026-W48.md").exists()


def test_write_note_atomic_overwrites(tmp_path):
    wp.write_note_atomic(tmp_path, "_surehub/planificacion/x.md", "uno")
    path = wp.write_note_atomic(tmp_path, "_surehub/planificacion/x.md", "dos")
    assert path.read_text(encoding="utf-8") == "dos"


def test_render_proposal_escapes_and_groups_by_day():
    out = {"week": "2026-W48", "start": "2026-11-23", "end": "2026-11-29", "summary": "<foco>",
           "events_considered": 3, "dropped": [{"title": "x", "reason": "r"}],
           "warnings": ["Sin revisión"],
           "blocks": [{"title": "A & B", "start": "2026-11-23T09:00:00", "end": "2026-11-23T12:00:00",
                       "theme": "padel"}]}
    text = wp.render_proposal(out)
    assert "&lt;foco&gt;" in text and "A &amp; B" in text
    assert "<b>Lun 23 nov</b>" in text
    assert "🟢 09:00–12:00" in text
    assert "1 descartados" in text and "⚠️ Sin revisión" in text
