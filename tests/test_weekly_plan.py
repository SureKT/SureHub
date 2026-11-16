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
    events = [PADEL, {**BDAY, "recurring": True}]
    prompt = wp.build_prompt(MON, SUN, "2026-W48", [("Tareas", "Tareas.md", "- [ ] DNI")], events,
                             previous={"summary": "s", "blocks": [{"title": "X"}]},
                             correction="mueve el gimnasio al jueves")
    assert "2026-11-23T20:30 → 22:00: Pádel" in prompt
    assert "(recurrente)" in prompt
    assert "Área: tarea concreta" in prompt   # shared conventions injected
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

    def engine(prompt, **kw):
        prompts.append(prompt)
        return EngineResult(text=_model([_block("App pádel", "2026-11-23T09:00", "2026-11-23T12:00"),
                                         _block("Gimnasio", "2026-11-24T08:00", "2026-11-24T09:00",
                                                "gimnasio")]),
                            cost_usd=0.02)

    monkeypatch.setattr(wp, "run_litellm", engine)
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
    monkeypatch.setattr(wp, "run_litellm", lambda *a, **k: EngineResult(text=_model([])))
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


# ── shared conventions + mid-week replanning ───────────────────────────────

PATTERNS = ["*: *", "Gym*"]


def _cal_event(id_, summary, start, end, color="4", recurring=False, description=""):
    return {"id": id_, "summary": summary, "start": start, "end": end, "all_day": False,
            "color_id": color, "surehub_run": None, "recurring": recurring, "description": description}


def test_conventions_note_created_once_and_patterns_parsed(tmp_path):
    path = wp.ensure_conventions(tmp_path)
    text, patterns = wp.load_conventions(tmp_path)
    assert patterns == PATTERNS
    assert "Área: tarea concreta" in text

    # the user owns it after creation: edits are kept and drive the rules
    path.write_text(text.replace("- `Gym*`", "- `Gym*`\n- `Escalada*`"), encoding="utf-8")
    wp.ensure_conventions(tmp_path)
    assert wp.load_conventions(tmp_path)[1] == ["*: *", "Gym*", "Escalada*"]


def test_split_events_by_shared_convention():
    events = [
        _cal_event("a", "App pádel: front", "2026-11-25T16:00:00", "2026-11-25T18:00:00"),   # chat-made block
        _cal_event("b", "Gym 2 (Pierna)", "2026-11-26T08:00:00", "2026-11-26T09:00:00", "9"),
        _cal_event("c", "Médico", "2026-11-26T10:00:00", "2026-11-26T11:00:00", "11"),
        _cal_event("d", "Cena: Rita", "2026-11-26T21:00:00", "2026-11-26T22:00:00", recurring=True),
        _cal_event("e", "Dinero: candidaturas", "2026-11-25T09:00:00", "2026-11-25T10:00:00", "8"),  # past
        {**BDAY, "recurring": False},
    ]
    fixed, movable = wp.split_events(events, datetime(2026, 11, 25, 15, 30), PATTERNS)
    assert [e["id"] for e in movable] == ["a", "b"]
    assert {e["id"] for e in fixed} == {"c", "d", "e", "e2"}


def test_replan_midweek_moves_chat_blocks_and_keeps_identical(session, fake_world, monkeypatch):
    # Wednesday: blocks created by the Claude chat (no SureHub metadata) + a new appointment
    thu = _cal_event("ev3", "App pádel: equilibrar parejas", "2026-11-26T09:00:00", "2026-11-26T12:00:00",
                     description="Algoritmo por nivel")
    keep = _cal_event("ev4", "Dinero: 3 candidaturas", "2026-11-27T12:00:00", "2026-11-27T13:00:00", "8")
    dentist = _cal_event("x1", "Dentista", "2026-11-26T09:30:00", "2026-11-26T10:30:00", "11")
    monkeypatch.setattr(calendar_api, "list_events", lambda s, e: [thu, keep, dentist])
    monkeypatch.setattr(wp, "run_litellm", lambda *a, **k: EngineResult(text=json.dumps({"summary": "s", "blocks": [
        {"title": "App pádel: equilibrar parejas", "start": "2026-11-26T10:30", "end": "2026-11-26T13:00",
         "theme": "formacion", "description": "Algoritmo por nivel"},
        {"title": "Dinero: 3 candidaturas", "start": "2026-11-27T12:00", "end": "2026-11-27T13:00", "theme": "default"},
    ]})))

    run = execute(session, ROUTINES["weekly_plan"], "manual", now=datetime(2026, 11, 25, 15, 10, tzinfo=TZ))
    out = load_json(run.output)
    assert out["start"] == "2026-11-25" and out["not_before"] == "2026-11-25T15:30"
    assert {e["id"] for e in out["replaces"]} == {"ev3", "ev4"}
    assert out["events_considered"] == 1                     # only the dentist is fixed
    assert "1 bloques se mantienen" in wp.render_proposal(out)
    assert (fake_world["vault"] / wp.CONVENTIONS_REL).exists()

    created, deleted = [], []
    monkeypatch.setattr(calendar_api, "create_event",
                        lambda *a, **k: created.append((a, k.get("description"))) or ("ev5", "l"))
    monkeypatch.setattr(calendar_api, "delete_event", deleted.append)
    result = wp.approve(session, run, fake_world["vault"])

    assert [(a[0], d) for a, d in created] == [("App pádel: equilibrar parejas", "Algoritmo por nivel")]
    assert deleted == ["ev3"]
    assert result["kept"] == {"1": "ev4"}

    # undo: delete new, recreate the replaced one with its color and description
    recreated = []
    monkeypatch.setattr(calendar_api, "create_event",
                        lambda *a, **k: recreated.append((a, k.get("description"))) or ("ev6", "l"))
    deleted.clear()
    assert wp.undo(session, run, fake_world["vault"]) == 1
    assert deleted == ["ev5"]
    assert recreated == [(("App pádel: equilibrar parejas", "2026-11-26T09:00:00", "2026-11-26T12:00:00",
                           False, "formacion"), "Algoritmo por nivel")]


def test_replan_appends_section_to_existing_week_note(session, fake_world, monkeypatch):
    week_note = fake_world["vault"] / "_surehub/planificacion/2026-W48.md"
    wp.write_note_atomic(fake_world["vault"], "_surehub/planificacion/2026-W48.md", "---\ntipo: plan-semanal\n---\nplan original")
    block = _cal_event("ev3", "App pádel: x", "2026-11-26T09:00:00", "2026-11-26T12:00:00")
    monkeypatch.setattr(calendar_api, "list_events", lambda s, e: [block])
    monkeypatch.setattr(wp, "run_litellm", lambda *a, **k: EngineResult(text=_model([
        _block("App pádel: x", "2026-11-26T16:00", "2026-11-26T18:00")])))
    run = execute(session, ROUTINES["weekly_plan"], "manual", now=datetime(2026, 11, 25, 15, 10, tzinfo=TZ))
    monkeypatch.setattr(calendar_api, "create_event", lambda *a, **k: ("n1", "l"))
    monkeypatch.setattr(calendar_api, "delete_event", lambda i: None)

    wp.approve(session, run, fake_world["vault"])
    text = week_note.read_text(encoding="utf-8")
    assert text.startswith("---\ntipo: plan-semanal\n---\nplan original")
    assert "# Reajuste desde Mié 25 nov 15:30" in text

    wp.undo(session, run, fake_world["vault"])
    assert week_note.read_text(encoding="utf-8") == "---\ntipo: plan-semanal\n---\nplan original"


def test_replan_prompt_lists_current_plan_as_movable():
    movable = [_cal_event("ev2", "Gym 2 (Pierna)", "2026-11-26T08:00:00", "2026-11-26T09:00:00", "9")]
    prompt = wp.build_prompt(date(2026, 11, 25), SUN, "2026-W48", [], [PADEL], movable=movable,
                             earliest=datetime(2026, 11, 25, 15, 30))
    assert "el resto de la semana 2026-W48" in prompt
    assert "Plan vigente" in prompt and "2026-11-26T08:00 → 09:00: Gym 2 (Pierna)" in prompt
    assert "15:30 del 25/11" in prompt
