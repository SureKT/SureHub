import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlmodel import Session

from app.config import settings
from app.database import engine
from app.services.llm import complete_tags, complete_event
from app.services.calendar import create_event as cal_create_event
from app.modules.inbox.service import (
    scan_inbox, pending_items, apply_item, apply_suggested, get_item, apply_event,
    extract_event, _today_str,
)
from bot.handlers import allowed, safe_reply


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


def build_digest(session) -> list[tuple[str, InlineKeyboardMarkup | None]]:
    items = pending_items(session)
    if not items:
        return []
    messages: list[tuple[str, InlineKeyboardMarkup | None]] = []

    confident = [i for i in items if i.category in ("task", "note")]
    if confident:
        lines = ["*Sugeridos* (los aplico en lote):"]
        for i in confident:
            icon = "✅" if i.category == "task" else "📄"
            lines.append(f"{icon} {i.proposed_text}")
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("✓ Aplicar sugeridos", callback_data="inbox:applyall")]]
        )
        messages.append(("\n".join(lines), kb))

    for i in items:
        if i.category != "uncertain":
            continue
        voice = " 🎤" if i.source == "telegram-voice" else ""
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✓ Tarea", callback_data=f"inbox:task:{i.id}"),
                InlineKeyboardButton("📄 Archivar", callback_data=f"inbox:note:{i.id}"),
            ],
            [
                InlineKeyboardButton("✗ Descartar", callback_data=f"inbox:discard:{i.id}"),
                InlineKeyboardButton("✏️ Editar", callback_data=f"inbox:edit:{i.id}"),
            ],
        ])
        messages.append((f"*Dudosa*{voice}:\n{i.excerpt}", kb))

    for i in items:
        if i.category == "event":
            messages.append(_event_card(i))

    return messages


def _scan_and_digest(vault_path) -> list[tuple[str, InlineKeyboardMarkup | None]]:
    """Runs in a worker thread: own session, LLM classification (slow), then
    builds detached (text, keyboard) tuples that outlive the session."""
    with Session(engine) as session:
        scan_inbox(session, vault_path, complete_tags, event_llm=complete_event)
        return build_digest(session)


async def cmd_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    await update.message.reply_chat_action("typing")
    messages = await asyncio.to_thread(_scan_and_digest, settings.OBSIDIAN_VAULT_PATH)
    if not messages:
        await safe_reply(update, "Inbox limpia ✅")
        return
    for text, kb in messages:
        await safe_reply(update, text, parse_mode="Markdown", reply_markup=kb)


async def _edit_or_send(update: Update, query, text: str):
    from telegram.error import BadRequest
    try:
        await query.edit_message_text(text)
    except BadRequest:
        await update.effective_chat.send_message(text)


async def callback_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # inbox:applyall | inbox:<action>:<id>

    if data == "inbox:applyall":
        with Session(engine) as session:
            counts = apply_suggested(session, settings.OBSIDIAN_VAULT_PATH)
        await _edit_or_send(
            update, query,
            f"✓ Aplicados: {counts['task']} tarea(s), {counts['note']} nota(s) archivada(s)."
        )
        return

    _, action, item_id_str = data.split(":")
    item_id = int(item_id_str)

    if action == "edit":
        context.user_data["inbox_edit_id"] = item_id
        await _edit_or_send(update, query, "Envíame el texto corregido de la tarea.")
        return

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
            try:
                _, link = apply_event(session, item, settings.OBSIDIAN_VAULT_PATH, cal_create_event)
            except Exception:
                await _edit_or_send(update, query, "No pude crear el evento (¿Google Calendar configurado?). La nota sigue pendiente.")
                return
        await _edit_or_send(update, query, f"📅 Evento creado: {link}")
        return

    with Session(engine) as session:
        item = get_item(session, item_id)
        if not item or item.status != "pending":
            await _edit_or_send(update, query, "Ya resuelta.")
            return
        apply_item(session, item, settings.OBSIDIAN_VAULT_PATH, action)

    labels = {"task": "✓ Tarea creada", "note": "📄 Archivada", "discard": "✗ Descartada"}
    await _edit_or_send(update, query, labels.get(action, "Hecho."))


async def apply_edited_task(update: Update, item_id: int, text: str) -> bool:
    """Applies `text` as the task for a pending item. Returns False if the item
    no longer exists / isn't pending (caller should fall through to normal handling)."""
    with Session(engine) as session:
        item = get_item(session, item_id)
        if not item or item.status != "pending":
            return False
        apply_item(session, item, settings.OBSIDIAN_VAULT_PATH, "task", override_text=text)
    await safe_reply(update, f"✓ Tarea creada: {text}")
    return True


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


async def inbox_digest_job(context: ContextTypes.DEFAULT_TYPE):
    """Daily scheduled scan + digest. Silent when there's nothing pending."""
    messages = await asyncio.to_thread(_scan_and_digest, settings.OBSIDIAN_VAULT_PATH)
    if not messages:
        return
    chat_id = settings.allowed_user_ids[0]
    for text, kb in messages:
        try:
            await context.bot.send_message(chat_id=chat_id, text=text,
                                           parse_mode="Markdown", reply_markup=kb)
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)
