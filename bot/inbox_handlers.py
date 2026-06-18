import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlmodel import Session

from app.config import settings
from app.database import engine
from app.services.llm import complete_tags
from app.modules.inbox.service import (
    scan_inbox, pending_items, apply_item, apply_suggested, get_item,
)
from bot.handlers import allowed, safe_reply


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

    return messages


def _scan_and_digest(vault_path) -> list[tuple[str, InlineKeyboardMarkup | None]]:
    """Runs in a worker thread: own session, LLM classification (slow), then
    builds detached (text, keyboard) tuples that outlive the session."""
    with Session(engine) as session:
        scan_inbox(session, vault_path, complete_tags)
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
