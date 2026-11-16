import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.modules.routines import weekly_plan as wp
from app.modules.routines.engines import EngineResult
from app.modules.routines.registry import ROUTINES
from app.modules.routines.service import RunContext, execute, load_json
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

W48 = "2026-W48"


@pytest.mark.parametrize("now,expected", [
    # any day, any hour: from the next 30-min slot until Sunday
    (datetime(2026, 11, 25, 15, 10, tzinfo=TZ), (date(2026, 11, 25), SUN, W48, datetime(2026, 11, 25, 15, 30))),
    (datetime(2026, 11, 25, 22, 0, tzinfo=TZ), (date(2026, 11, 25), SUN, W48, datetime(2026, 11, 25, 22, 30))),
    (datetime(2026, 11, 23, 8, 0, tzinfo=TZ), (MON, SUN, W48, datetime(2026, 11, 23, 8, 30))),
    # Sunday itself can be replanned...
    (datetime(2026, 11, 29, 10, 0, tzinfo=TZ), (SUN, SUN, W48, datetime(2026, 11, 29, 10, 30))),
    # ...until less than 2h are left in the week → next week
    (datetime(2026, 11, 29, 22, 15, tzinfo=TZ), (date(2026, 11, 30), date(2026, 12, 6), "2026-W49",
                                                 datetime(2026, 11, 30, 0, 0))),
])
def test_plan_window_rest_of_week(now, expected):
    assert wp.plan_window(now, "rest") == expected


@pytest.mark.parametrize("now", [datetime(2026, 11, 22, 19, tzinfo=TZ), datetime(2026, 11, 18, 11, tzinfo=TZ)])
def test_plan_window_next_week(now):
    start, end, label, earliest = wp.plan_window(now, "next")
    if now.weekday() == 6:
        assert (start, end, label) == (MON, SUN, W48)
    else:
        assert (start, end, label) == (MON, SUN, W48)
    assert earliest == datetime(2026, 11, 23, 0, 0)


def test_year_boundary_week_label():
    assert wp.plan_window(datetime(2026, 12, 27, 19, tzinfo=TZ), "next")[:3] == (
        date(2026, 12, 28), date(2027, 1, 3), "2026-W53")


@pytest.mark.parametrize("trigger,now,options,expected", [
    ("scheduled", datetime(2026, 11, 22, 19, tzinfo=TZ), {}, "next"),
    ("catch_up", datetime(2026, 11, 22, 23, tzinfo=TZ), {}, "next"),
    ("catch_up", datetime(2026, 11, 23, 8, tzinfo=TZ), {}, "rest"),   # Monday: the week just started
    ("manual", datetime(2026, 11, 22, 11, tzinfo=TZ), {}, "rest"),
    ("manual", datetime(2026, 11, 25, 11, tzinfo=TZ), {"scope": "next"}, "next"),
])
def test_resolve_scope(trigger, now, options, expected):
    ctx = RunContext(now=now, trigger=trigger, options=options)
    assert wp.resolve_scope(ctx) == expected


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
        _block("Recordatorio", "2026-11-25T17:00", "2026-11-25T17:15"),
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
    assert reasons["Recordatorio"] == "duración inválida"   # < 30 min
    assert reasons["Choca consigo"] == "se solapa con un evento existente"
    assert reasons["sin fechas"] == "formato inválido"


def test_blocks_before_now_are_dropped():
    p = wp.parse_proposal(_model([_block("Tarde", "2026-11-25T15:00", "2026-11-25T16:00"),
                                  _block("Luego", "2026-11-25T17:00", "2026-11-25T18:00")]),
                          date(2026, 11, 25), SUN, [], earliest=datetime(2026, 11, 25, 15, 30))
    assert [b["title"] for b in p["blocks"]] == ["Luego"]
    assert p["dropped"][0]["reason"] == "en el pasado"


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
    assert "Plan vigente" not in prompt   # no movable blocks → no section
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
    run = execute(session, ROUTINES["weekly_plan"], "scheduled",
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
    run = execute(session, ROUTINES["weekly_plan"], "scheduled",
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


# ── mid-week replanning ─────────────────────────────────────────────────────

def _approved_sunday_plan(session, fake_world, monkeypatch):
    """Sunday run approved: creates ev1 (Mon 9-12) and ev2 (Tue 8-9)."""
    run = execute(session, ROUTINES["weekly_plan"], "scheduled",
                  now=datetime(2026, 11, 22, 19, tzinfo=TZ))
    ids = iter(["ev1", "ev2"])
    monkeypatch.setattr(calendar_api, "create_event", lambda *a, **k: (next(ids), "l"))
    wp.approve(session, run, fake_world["vault"])
    return run


def _cal_event(id_, summary, start, end, run_id=None, color="4"):
    return {"id": id_, "summary": summary, "start": start, "end": end, "all_day": False,
            "color_id": color, "surehub_run": str(run_id) if run_id else None}


def test_split_events_fixed_vs_movable(session, fake_world, monkeypatch):
    sunday = _approved_sunday_plan(session, fake_world, monkeypatch)
    events = [
        PADEL,                                                                     # not SureHub
        _cal_event("ev1", "App pádel", "2026-11-23T10:00:00", "2026-11-23T13:00:00", sunday.id),  # moved by hand
        _cal_event("ev2", "Gimnasio", "2026-11-24T08:00:00", "2026-11-24T09:00:00", sunday.id),   # untouched
        _cal_event("ev9", "Huérfano", "2026-11-24T10:00:00", "2026-11-24T11:00:00", 999),        # unknown run
    ]
    fixed, movable = wp.split_events(session, events, datetime(2026, 11, 23, 0, 0))
    assert [e["id"] for e in movable] == ["ev2"]
    assert {e["id"] for e in fixed} == {"e1", "ev1", "ev9"}

    # once its time has passed an untouched block is no longer movable
    _, movable = wp.split_events(session, events, datetime(2026, 11, 24, 12, 0))
    assert movable == []


def test_replan_midweek_replaces_untouched_blocks_and_appends_note(session, fake_world, monkeypatch):
    sunday = _approved_sunday_plan(session, fake_world, monkeypatch)
    # Wednesday: Sunday's Thu block is still untouched, a new fixed event appeared
    thu = _cal_event("ev3", "Proyecto jueves", "2026-11-26T09:00:00", "2026-11-26T12:00:00", sunday.id)
    keep = _cal_event("ev4", "Candidaturas", "2026-11-27T12:00:00", "2026-11-27T13:00:00", sunday.id, "8")
    dentist = _cal_event("x1", "Dentista", "2026-11-26T09:30:00", "2026-11-26T10:30:00")
    sunday.output = json.dumps({**load_json(sunday.output), "blocks": load_json(sunday.output)["blocks"] + [
        {"title": "Proyecto jueves", "start": "2026-11-26T09:00:00", "end": "2026-11-26T12:00:00", "theme": "formacion"},
        {"title": "Candidaturas", "start": "2026-11-27T12:00:00", "end": "2026-11-27T13:00:00", "theme": "default"},
    ]})
    sunday.result = json.dumps({**load_json(sunday.result),
                                "created": {**load_json(sunday.result)["created"], "2": "ev3", "3": "ev4"}})
    session.add(sunday); session.commit()
    monkeypatch.setattr(calendar_api, "list_events", lambda s, e: [thu, keep, dentist])
    monkeypatch.setattr(wp, "run_engine", lambda *a, **k: EngineResult(text=_model([
        _block("Proyecto jueves", "2026-11-26T10:30", "2026-11-26T13:00"),     # moved around the dentist
        _block("Candidaturas", "2026-11-27T12:00", "2026-11-27T13:00", "default"),  # unchanged
    ])))

    run = execute(session, ROUTINES["weekly_plan"], "manual", now=datetime(2026, 11, 25, 15, 10, tzinfo=TZ))
    out = load_json(run.output)
    assert out["start"] == "2026-11-25" and out["not_before"] == "2026-11-25T15:30"
    assert {e["id"] for e in out["replaces"]} == {"ev3", "ev4"}
    assert out["events_considered"] == 1                     # only the dentist is fixed
    assert "♻️" in wp.render_proposal(out) and "1 bloques se mantienen" in wp.render_proposal(out)

    created, deleted = [], []
    monkeypatch.setattr(calendar_api, "create_event", lambda *a, **k: created.append(a[0]) or ("ev5", "l"))
    monkeypatch.setattr(calendar_api, "delete_event", deleted.append)
    result = wp.approve(session, run, fake_world["vault"])

    assert created == ["Proyecto jueves"]                    # unchanged one is kept, not recreated
    assert deleted == ["ev3"]
    assert result["kept"] == {"1": "ev4"}
    note = (fake_world["vault"] / "_surehub/planificacion/2026-W48.md").read_text(encoding="utf-8")
    assert note.startswith("---\ntipo: plan-semanal")      # original note preserved
    assert "# Reajuste desde Mié 25 nov 15:30" in note

    # undo: delete new, recreate replaced (same color), restore note
    recreated = []
    monkeypatch.setattr(calendar_api, "create_event", lambda *a, **k: recreated.append(a) or ("ev6", "l"))
    deleted.clear()
    assert wp.undo(session, run, fake_world["vault"]) == 1
    assert deleted == ["ev5"]
    assert recreated == [("Proyecto jueves", "2026-11-26T09:00:00", "2026-11-26T12:00:00", False, "formacion")]
    restored = (fake_world["vault"] / "_surehub/planificacion/2026-W48.md").read_text(encoding="utf-8")
    assert "Reajuste" not in restored


def test_replan_prompt_lists_current_plan_as_movable():
    movable = [_cal_event("ev2", "Gimnasio", "2026-11-26T08:00:00", "2026-11-26T09:00:00", 1)]
    prompt = wp.build_prompt(date(2026, 11, 25), SUN, "2026-W48", [], [PADEL], movable=movable,
                             earliest=datetime(2026, 11, 25, 15, 30))
    assert "el resto de la semana 2026-W48" in prompt
    assert "Plan vigente" in prompt and "2026-11-26T08:00 → 09:00: Gimnasio" in prompt
    assert "15:30 del 25/11" in prompt
