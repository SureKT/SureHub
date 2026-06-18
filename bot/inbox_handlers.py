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
