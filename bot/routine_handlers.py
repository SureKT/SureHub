"""Telegram side of routines: scheduling (JobQueue), /plan, /routines and the
approval flow (Aprobar / Ajustar / Descartar / Deshacer)."""
import asyncio
import html
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlmodel import Session
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import Application, ContextTypes

from app.config import settings
from app.database import engine
from app.modules.routines import weekly_plan, weekly_review
from app.modules.routines.models import RoutineRun
from app.modules.routines.registry import ROUTINES
from app.modules.routines.service import execute, get_run, list_runs, load_json, needs_catch_up
from bot.handlers import allowed, safe_reply, _edit_or_send

logger = logging.getLogger("surehub.bot")

ADJUST_KEY = "routine_adjust_run_id"
REVIEW_KEY = "routine_review_run_id"
CATCH_UP_DELAY_S = 30

# Runs with a side effect in progress (approve/undo). Single bot process, so an
# in-memory guard is enough to stop a double tap from creating events twice.
_in_flight: set[int] = set()

STATUS_ES = {
    "running": "en curso", "succeeded": "ok", "failed": "❌ falló",
    "awaiting_approval": "⏳ pendiente", "approving": "aplicando", "approved": "✅ aprobada",
    "discarded": "descartada", "superseded": "reemplazada", "undone": "↩️ deshecha",
    "awaiting_input": "⏳ esperando respuesta", "skipped": "saltada",
}


def _chat_id() -> int:
    return settings.allowed_user_ids[0]


def _proposal_keyboard(run_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Aprobar", callback_data=f"rt:approve:{run_id}"),
        InlineKeyboardButton("✏️ Ajustar", callback_data=f"rt:adjust:{run_id}"),
        InlineKeyboardButton("🗑 Descartar", callback_data=f"rt:discard:{run_id}"),
    ]])


def _review_keyboard(run_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🎤 Responder", callback_data=f"rt:answer:{run_id}"),
        InlineKeyboardButton("⏭ Saltar y planificar", callback_data=f"rt:skip:{run_id}"),
    ]])


def _undo_keyboard(run_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("↩️ Deshacer semana", callback_data=f"rt:undo:{run_id}"),
    ]])


def render_run(run: RoutineRun) -> tuple[str, InlineKeyboardMarkup | None]:
    routine = ROUTINES.get(run.routine_key)
    name = html.escape(routine.name if routine else run.routine_key)
    if run.status == "failed":
        return f"⚠️ <b>Rutina «{name}» falló</b>\n<code>{html.escape(run.error or '')[:800]}</code>", None
    if run.routine_key == weekly_plan.KEY and run.status == "awaiting_approval":
        return weekly_plan.render_proposal(load_json(run.output)), _proposal_keyboard(run.id)
    if run.routine_key == weekly_review.KEY and run.status == "awaiting_input":
        return weekly_review.render_questions(load_json(run.output)), _review_keyboard(run.id)
    return f"✓ Rutina «{name}»: {STATUS_ES.get(run.status, run.status)}", None


def _plain(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text))


async def _send(bot, text: str, kb=None):
    try:
        return await bot.send_message(chat_id=_chat_id(), text=text, parse_mode="HTML", reply_markup=kb)
    except BadRequest:
        return await bot.send_message(chat_id=_chat_id(), text=_plain(text), reply_markup=kb)


def _execute_sync(key: str, trigger: str, parent_id: int | None = None,
                  correction: str | None = None, options: dict | None = None) -> RoutineRun:
    with Session(engine) as session:
        parent = get_run(session, parent_id) if parent_id else None
        return execute(session, ROUTINES[key], trigger, parent=parent, correction=correction,
                       options=options)


async def run_and_deliver(bot, key: str, trigger: str, parent_id: int | None = None,
                          correction: str | None = None, options: dict | None = None) -> RoutineRun:
    run = await asyncio.to_thread(_execute_sync, key, trigger, parent_id, correction, options)
    text, kb = render_run(run)
    msg = await _send(bot, text, kb)
    if run.status == "awaiting_input" and getattr(msg, "message_id", None):
        # Lets the user answer by replying to the message, even after a bot restart.
        await asyncio.to_thread(_store_message_id, run.id, msg.message_id)
    return run


def _store_message_id(run_id: int, message_id: int) -> None:
    with Session(engine) as session:
        run = get_run(session, run_id)
        result = load_json(run.result) or {}
        result["message_id"] = message_id
        run.result = json.dumps(result)
        session.add(run)
        session.commit()


def pending_review_for_reply(message_id: int) -> int | None:
    with Session(engine) as session:
        for run in list_runs(session, weekly_review.KEY, limit=10):
            if run.status == "awaiting_input" and load_json(run.result).get("message_id") == message_id:
                return run.id
    return None


async def routine_job(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    await run_and_deliver(context.bot, data["key"], data["trigger"])


def schedule_routines(app: Application) -> None:
    for r in ROUTINES.values():
        if r.trigger() is None:
            continue
        app.job_queue.run_custom(
            routine_job,
            job_kwargs={"trigger": r.trigger(), "misfire_grace_time": 3600, "coalesce": True},
            data={"key": r.key, "trigger": "scheduled"},
            name=f"routine:{r.key}",
        )
    # JobQueue is in-memory: a deploy/restart at fire time would silently skip the
    # run. RoutineRun is the source of truth to detect and recover it.
    with Session(engine) as session:
        for r in ROUTINES.values():
            if needs_catch_up(session, r, datetime.now(ZoneInfo(r.timezone))):
                logger.info("Routine %s missed its last fire → catch-up", r.key)
                app.job_queue.run_once(routine_job, when=CATCH_UP_DELAY_S,
                                       data={"key": r.key, "trigger": "catch_up"},
                                       name=f"routine-catchup:{r.key}")


# ── commands ────────────────────────────────────────────────────────────────

NEXT_WEEK_ARGS = {"semana", "siguiente", "proxima", "próxima", "next"}


def plan_scope(args: list[str]) -> str:
    return "next" if any(a.lower() in NEXT_WEEK_ARGS for a in args) else "rest"


async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/plan → replan from now until Sunday · /plan semana → the whole next week."""
    if not allowed(update):
        return
    scope = plan_scope(context.args or [])
    label = "la semana que viene" if scope == "next" else "desde ahora hasta el domingo"
    await safe_reply(update, f"🗓 Generando propuesta ({label})…")
    await update.message.reply_chat_action("typing")
    await run_and_deliver(context.bot, weekly_plan.KEY, "manual", options={"scope": scope})


async def cmd_routines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    with Session(engine) as session:
        lines = ["<b>Rutinas</b>"]
        buttons = []
        for r in ROUTINES.values():
            when = f"<code>{r.cron}</code>" if r.cron else "bajo demanda"
            lines.append(f"• <b>{html.escape(r.name)}</b> — {when} ({r.engine})")
            buttons.append([InlineKeyboardButton(f"▶️ {r.name}", callback_data=f"rt:run:{r.key}")])
        runs = list_runs(session, limit=5)
        if runs:
            lines.append("\n<b>Últimos runs</b>")
            for run in runs:
                cost = f" · ${run.cost_usd:.3f}" if run.cost_usd else ""
                lines.append(f"#{run.id} {run.routine_key} · {STATUS_ES.get(run.status, run.status)}"
                             f" · {run.trigger} · {run.started_at:%d/%m %H:%M} UTC{cost}")
    await safe_reply(update, "\n".join(lines), parse_mode="HTML",
                     reply_markup=InlineKeyboardMarkup(buttons))


# ── approval flow ───────────────────────────────────────────────────────────

def _approve_sync(run_id: int) -> dict:
    with Session(engine) as session:
        run = get_run(session, run_id)
        return weekly_plan.approve(session, run, Path(settings.OBSIDIAN_VAULT_PATH))


def _undo_sync(run_id: int) -> int:
    with Session(engine) as session:
        run = get_run(session, run_id)
        return weekly_plan.undo(session, run, Path(settings.OBSIDIAN_VAULT_PATH))


def _skip_sync(run_id: int) -> None:
    with Session(engine) as session:
        weekly_review.skip(session, get_run(session, run_id))


def _complete_review_sync(run_id: int, text: str) -> dict:
    with Session(engine) as session:
        return weekly_review.complete(session, get_run(session, run_id), text,
                                      Path(settings.OBSIDIAN_VAULT_PATH))


def _set_status(run_id: int, status: str) -> None:
    with Session(engine) as session:
        run = get_run(session, run_id)
        run.status = status
        session.add(run)
        session.commit()


def _status(run_id: int) -> str | None:
    with Session(engine) as session:
        run = get_run(session, run_id)
        return run.status if run else None


async def callback_routine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    query = update.callback_query
    await query.answer()
    _, action, arg = query.data.split(":", 2)

    if action == "run":
        if arg not in ROUTINES:
            await _edit_or_send(update, query, "Rutina desconocida.")
            return
        await _edit_or_send(update, query, f"▶️ Ejecutando «{ROUTINES[arg].name}»…")
        await run_and_deliver(context.bot, arg, "manual")
        return

    run_id = int(arg)
    if run_id in _in_flight:
        await update.effective_chat.send_message("⏳ Ya se está aplicando, espera.")
        return
    status = _status(run_id)

    if action == "answer":
        if status != "awaiting_input":
            await _edit_or_send(update, query, "Esta revisión ya no está pendiente.")
            return
        context.user_data[REVIEW_KEY] = run_id
        await update.effective_chat.send_message(
            "🎤 Te escucho: manda un audio o un texto con todas tus respuestas.")
        return

    if action == "skip":
        if status != "awaiting_input":
            await _edit_or_send(update, query, "Esta revisión ya no está pendiente.")
            return
        await asyncio.to_thread(_skip_sync, run_id)
        await _edit_or_send(update, query, "⏭ Revisión saltada. Preparo el plan…")
        await run_and_deliver(context.bot, weekly_plan.KEY, "after_review")
        return

    if action == "approve":
        if status not in ("awaiting_approval", "approving"):
            await _edit_or_send(update, query, "Esta propuesta ya no está activa.")
            return
        _in_flight.add(run_id)
        try:
            result = await asyncio.to_thread(_approve_sync, run_id)
        except Exception as e:
            logger.exception("Approve of run %s failed", run_id)
            await update.effective_chat.send_message(
                f"⚠️ Error al aplicar ({type(e).__name__}). Lo creado se conserva; "
                "pulsa ✅ Aprobar otra vez para reintentar sin duplicar.")
            return
        finally:
            _in_flight.discard(run_id)
        await _edit_or_send(
            update, query,
            f"✅ Semana aprobada: {len(result['created'])} eventos en Calendar.\n📝 {result['note']}",
            reply_markup=_undo_keyboard(run_id),
        )
        return

    if action == "adjust":
        if status != "awaiting_approval":
            await _edit_or_send(update, query, "Esta propuesta ya no está activa.")
            return
        context.user_data[ADJUST_KEY] = run_id
        await update.effective_chat.send_message("✏️ Envíame la corrección (texto o 🎤 audio).")
        return

    if action == "discard":
        if status != "awaiting_approval":
            await _edit_or_send(update, query, "Esta propuesta ya no está activa.")
            return
        await asyncio.to_thread(_set_status, run_id, "discarded")
        await _edit_or_send(update, query, "🗑 Propuesta descartada.")
        return

    if action == "undo":
        if status != "approved":
            await _edit_or_send(update, query, "No hay nada que deshacer.")
            return
        _in_flight.add(run_id)
        try:
            n = await asyncio.to_thread(_undo_sync, run_id)
        except Exception as e:
            logger.exception("Undo of run %s failed", run_id)
            await update.effective_chat.send_message(
                f"⚠️ Error al deshacer ({type(e).__name__}). Pulsa ↩️ otra vez para reintentar.")
            return
        finally:
            _in_flight.discard(run_id)
        await _edit_or_send(update, query, f"↩️ Semana deshecha: {n} eventos borrados y nota eliminada.")


async def apply_adjustment(update: Update, context: ContextTypes.DEFAULT_TYPE,
                           run_id: int, text: str) -> bool:
    """Regenerate a pending proposal with the user's correction. False if the run is
    no longer pending (the text then follows the normal capture path)."""
    run_status = await asyncio.to_thread(_status, run_id)
    if run_status != "awaiting_approval":
        return False
    with Session(engine) as session:
        key = get_run(session, run_id).routine_key
    await safe_reply(update, "🔁 Regenerando con tu corrección…")
    await update.message.reply_chat_action("typing")
    await run_and_deliver(context.bot, key, "adjust", parent_id=run_id, correction=text)
    return True


async def apply_review_answer(update: Update, context: ContextTypes.DEFAULT_TYPE,
                              run_id: int, text: str) -> bool:
    """Save the review answer, send the copy-paste summary, then launch the plan.
    False if the review is no longer pending (text follows the normal capture path)."""
    if await asyncio.to_thread(_status, run_id) != "awaiting_input":
        return False
    await safe_reply(update, "📝 Ordenando tu revisión…")
    await update.message.reply_chat_action("typing")
    out = await asyncio.to_thread(_complete_review_sync, run_id, text)
    note = html.escape(out["note"])
    warn = "\n⚠️ No pude ordenarla: guardada tal cual." if out.get("structure_error") else ""
    await _send(context.bot, f"✅ Revisión guardada: <code>{note}</code>{warn}\n\n"
                             f"<b>Resumen para el chat de planificación</b> (por si el vault no está sincronizado):\n"
                             f"<pre>{html.escape(out['summary'])}</pre>")
    await _send(context.bot, "🗓 Preparando el plan de la semana…")
    await run_and_deliver(context.bot, weekly_plan.KEY, "after_review")
    return True
