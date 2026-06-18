import asyncio
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from app.config import settings
from app.database import get_session, engine
from app.services.llm import chat, complete_tags
from app.modules.finanzas.models import Expense, Category
from app.modules.finanzas.parser import parse_expense
from app.modules.finanzas.service import (
    register_expense, latest_expenses, month_total,
    month_summary, find_category, list_categories, get_expenses_filtered,
)
from app.modules.memoria.service import build_context
from app.modules.notes.service import create_note, extract_tags
from app.services.transcribe import transcribe
from bot.help_text import HELP, WELCOME
from sqlmodel import Session

NOTE_PREFIX = "."
logger = logging.getLogger("surehub.bot")

MONTHS_ES = ["enero","febrero","marzo","abril","mayo","junio",
             "julio","agosto","septiembre","octubre","noviembre","diciembre"]


def allowed(update: Update) -> bool:
    return update.effective_user.id in settings.allowed_user_ids


async def safe_reply(update: Update, text: str, **kwargs):
    """Responde garantizando entrega: si el Markdown está mal formado (BadRequest),
    reintenta en texto plano. La captura nunca debe perderse de cara al usuario."""
    try:
        await update.message.reply_text(text, **kwargs)
    except BadRequest:
        kwargs.pop("parse_mode", None)
        await update.message.reply_text(text, **kwargs)


async def _edit_or_send(update: Update, query, text: str, **kwargs):
    """Edita el mensaje del callback. Ante BadRequest reintenta sin Markdown; si aun
    así falla (mensaje borrado del chat), manda uno nuevo en texto plano."""
    try:
        await query.edit_message_text(text, **kwargs)
    except BadRequest:
        kwargs.pop("parse_mode", None)
        try:
            await query.edit_message_text(text, **kwargs)
        except BadRequest:
            await update.effective_chat.send_message(text, **kwargs)


def _bar(total: float, estimate: float) -> str:
    if estimate <= 0:
        return ""
    pct = min(total / estimate, 1.0)
    filled = round(pct * 8)
    return f" `{'█' * filled}{'░' * (8 - filled)}`"


def _build_finance_context(session) -> str:
    now = datetime.now(timezone.utc)
    total = month_total(session)
    summary = month_summary(session)
    if not summary and total == 0:
        return ""
    month_name = MONTHS_ES[now.month - 1]
    lines = [f"Gastos {month_name} {now.year} (datos reales):"]
    lines.append(f"- Total: {total:.2f}€")
    for r in sorted(summary, key=lambda x: x["total"], reverse=True):
        if r["total"] > 0:
            est = f"/{r['estimate']:.0f}€" if r["estimate"] > 0 else ""
            alert = " [SOBRE PRESUPUESTO]" if r["alert"] else ""
            lines.append(f"- {r['name']}: {r['total']:.2f}€{est}{alert}")
    return "\n".join(lines)


def _category_keyboard(session) -> InlineKeyboardMarkup:
    cats = list_categories(session)[:8]
    buttons = [InlineKeyboardButton(c.name, callback_data=f"cat:{c.id}") for c in cats]
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton("Sin categoría", callback_data="cat:0")])
    return InlineKeyboardMarkup(rows)


def note_text_from_message(text: str) -> str | None:
    """Free text or `. prefix` → Obsidian note. Expense parser takes priority in message()."""
    raw = text.strip()
    if raw.startswith(NOTE_PREFIX):
        inner = raw[len(NOTE_PREFIX):].strip()
        return inner or None
    if " " in raw and len(raw) >= 4:
        return raw
    return None


async def _save_and_reply_note(update: Update, text: str, *, source: str = "telegram", label: str = "Nota guardada"):
    await update.message.reply_chat_action("typing")
    path = await asyncio.to_thread(create_note, text, settings.OBSIDIAN_VAULT_PATH, complete_tags, source, settings.TIMEZONE)
    tags = extract_tags(path)
    tags_str = f" · tags: {', '.join(tags)}" if tags else " · sin tags"
    await safe_reply(update,f"{label}: {path.name}{tags_str}")


async def voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    voice = update.message.voice
    if not voice:
        return

    await update.message.reply_chat_action("typing")
    tg_file = await context.bot.get_file(voice.file_id)

    with tempfile.TemporaryDirectory() as tmp:
        audio_path = Path(tmp) / "voice.ogg"
        await tg_file.download_to_drive(str(audio_path))
        try:
            text = await asyncio.to_thread(transcribe, audio_path)
        except Exception as exc:
            logger.exception("Voice transcription failed: %s", exc)
            await safe_reply(update,"No pude transcribir el audio. Inténtalo de nuevo.")
            return

    if not text.strip():
        await safe_reply(update,"El audio no tenía texto reconocible.")
        return

    await _save_and_reply_note(update, text, source="telegram-voice", label="Nota guardada (voz)")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    await safe_reply(update,WELCOME, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    await safe_reply(update,HELP, parse_mode="Markdown")


async def cmd_gastos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    filter_month = context.args and context.args[0].lower() in ("mes", "month")

    with Session(engine) as session:
        if filter_month:
            now = datetime.now(timezone.utc)
            expenses_raw, total_count = get_expenses_filtered(
                session, year=now.year, month=now.month,
                page=1, per_page=15, order="date", asc=False
            )
        else:
            expenses_raw = latest_expenses(session, 10)
            total_count = len(expenses_raw)

        if not expenses_raw:
            await safe_reply(update,"Sin gastos registrados.")
            return

        lines = []
        for e, cat in expenses_raw:
            cat_name = cat.name if cat else "—"
            desc = f" {e.description}" if e.description else ""
            date = e.date.strftime("%d/%m") if e.date else ""
            lines.append(f"`{e.id:4d}` {date}  *{e.amount:.2f}€*  {cat_name}{desc}")

        header = f"Mes actual ({total_count} gastos):" if filter_month else "Últimos gastos:"

    await safe_reply(update,header + "\n" + "\n".join(lines), parse_mode="Markdown")


async def cmd_borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    if not context.args:
        await safe_reply(update,"Uso: /borrar <id>")
        return
    try:
        expense_id = int(context.args[0])
    except ValueError:
        await safe_reply(update,"ID debe ser un número.")
        return

    with Session(engine) as session:
        expense = session.get(Expense, expense_id)
        if not expense:
            await safe_reply(update,f"No existe el gasto #{expense_id}.")
            return

        cat = session.get(Category, expense.category_id) if expense.category_id else None
        cat_name = cat.name if cat else "sin categoría"
        desc = f" — {expense.description}" if expense.description else ""
        amount = expense.amount

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✓ Confirmar", callback_data=f"borrar:{expense_id}"),
        InlineKeyboardButton("✕ Cancelar", callback_data="borrar:cancel"),
    ]])
    await safe_reply(update,
        f"Borrar gasto #{expense_id}?\n`{amount:.2f}€`  {cat_name}{desc}",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def callback_borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "borrar:cancel":
        await _edit_or_send(update, query, "Cancelado.")
        return

    expense_id = int(query.data.split(":")[1])
    with Session(engine) as session:
        expense = session.get(Expense, expense_id)
        if not expense:
            await _edit_or_send(update, query, "No encontrado.")
            return
        session.delete(expense)
        session.commit()
    await _edit_or_send(update, query, f"✓ Gasto #{expense_id} eliminado.")


async def callback_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pending = context.user_data.get("pending_expense")
    if not pending:
        await _edit_or_send(update, query, "Sin gasto pendiente.")
        return

    cat_id_str = query.data.split(":")[1]
    cat_id = int(cat_id_str) if cat_id_str != "0" else None

    with Session(engine) as session:
        register_expense(session, pending["amount"], cat_id, pending["description"])
        cat = session.get(Category, cat_id) if cat_id else None
        cat_name = cat.name if cat else "sin categoría"

    context.user_data.pop("pending_expense", None)
    await _edit_or_send(
        update, query,
        f"✓ *{pending['description']}* — {pending['amount']:.2f}€ ({cat_name})",
        parse_mode="Markdown"
    )


async def cmd_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        summary = month_summary(session)
        total = month_total(session)
        prev_month = now.month - 1 or 12
        prev_year = now.year if now.month > 1 else now.year - 1
        prev_total = month_total(session, prev_year, prev_month)

    if not summary:
        await safe_reply(update,"Sin categorías. Configúralas desde el dashboard.")
        return

    month_name = MONTHS_ES[now.month - 1].capitalize()
    lines = [f"*{month_name} {now.year}*"]

    if prev_total > 0:
        pct = ((total - prev_total) / prev_total) * 100
        sign = "+" if pct >= 0 else ""
        arrow = "▲" if pct > 5 else ("▼" if pct < -5 else "→")
        lines.append(f"{arrow} {sign}{pct:.0f}% vs {MONTHS_ES[prev_month - 1]}")

    alerts = [r for r in summary if r["alert"]]
    if alerts:
        lines.append(f"⚠ Sobre presupuesto: {', '.join(a['name'] for a in alerts)}")

    variable = [r for r in summary if r["type"] == "variable" and (r["total"] > 0 or r["estimate"] > 0)]
    fixed = [r for r in summary if r["type"] == "fixed" and (r["total"] > 0 or r["estimate"] > 0)]

    for section, items in [("Variable", variable), ("Fijo", fixed)]:
        if not items:
            continue
        lines.append(f"\n*{section}*")
        for r in items:
            alert = " ⚠" if r["alert"] else ""
            bar = _bar(r["total"], r["estimate"])
            est = f"/{r['estimate']:.0f}€" if r["estimate"] > 0 else ""
            lines.append(f"  {r['name']}: {r['total']:.0f}€{est}{alert}{bar}")

    lines.append(f"\n*Total: {total:.2f}€*")
    await safe_reply(update,"\n".join(lines), parse_mode="Markdown")


async def cmd_categorias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    with Session(engine) as session:
        cats = list_categories(session)

    if not cats:
        await safe_reply(update,"Sin categorías.")
        return
    variable = [c for c in cats if c.type == "variable"]
    fixed = [c for c in cats if c.type == "fixed"]
    lines = ["*Variable*"] + [f"  {c.name}" + (f" — {c.monthly_estimate:.0f}€/mes" if c.monthly_estimate > 0 else "") for c in variable]
    if fixed:
        lines += ["\n*Fijo*"] + [f"  {c.name}" + (f" — {c.monthly_estimate:.0f}€/mes" if c.monthly_estimate > 0 else "") for c in fixed]
    await safe_reply(update,"\n".join(lines), parse_mode="Markdown")


async def cmd_nota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    text = " ".join(context.args).strip()
    if not text:
        await safe_reply(update,"Uso: /nota <texto>\nTambién puedes escribir texto libre o `. nota` sin comando.")
        return
    await _save_and_reply_note(update, text)


DEFAULT_ANALISIS_QUESTION = (
    "Analiza mis gastos de este mes. ¿En qué destaco positiva o negativamente? ¿Algún consejo concreto?"
)


async def cmd_analisis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    question = " ".join(context.args).strip() if context.args else DEFAULT_ANALISIS_QUESTION
    context.user_data["pending_analisis"] = question
    preview = question if len(question) <= 120 else question[:117] + "…"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✓ Analizar", callback_data="analisis:confirm"),
        InlineKeyboardButton("✕ Cancelar", callback_data="analisis:cancel"),
    ]])
    await safe_reply(update,
        "*Análisis IA* (Claude Sonnet, tiene coste)\n\n"
        f"_{preview}_\n\n"
        "¿Continuar?",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def callback_analisis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "analisis:cancel":
        context.user_data.pop("pending_analisis", None)
        await _edit_or_send(update, query, "Cancelado.")
        return

    question = context.user_data.pop("pending_analisis", None)
    if not question:
        await _edit_or_send(update, query, "Expirado. Vuelve a lanzar /analisis.")
        return

    await query.edit_message_text("Analizando…")
    with Session(engine) as session:
        memory_context = build_context(session)
        finance_context = _build_finance_context(session)
    response = await asyncio.to_thread(chat, question, memory_context, finance_context)
    await safe_reply(update, response, parse_mode="Markdown")


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    edit_id = context.user_data.pop("inbox_edit_id", None)
    if edit_id is not None:
        from bot.inbox_handlers import apply_edited_task
        if await apply_edited_task(update, edit_id, update.message.text.strip()):
            return
    event_edit_id = context.user_data.pop("inbox_event_edit_id", None)
    if event_edit_id is not None:
        from bot.inbox_handlers import reextract_event_date
        if await reextract_event_date(update, event_edit_id, update.message.text.strip()):
            return
    text = update.message.text

    parsed = parse_expense(text)
    if parsed:
        with Session(engine) as session:
            cat = find_category(session, parsed.category_hint) if parsed.category_hint else None

            if cat:
                register_expense(session, parsed.amount, cat.id, parsed.description)
                await safe_reply(update,
                    f"✓ *{parsed.description}* — {parsed.amount:.2f}€ ({cat.name})",
                    parse_mode="Markdown"
                )
            else:
                context.user_data["pending_expense"] = {
                    "description": parsed.description,
                    "amount": parsed.amount,
                }
                await safe_reply(update,
                    f"*{parsed.description}* — {parsed.amount:.2f}€\n¿Categoría?",
                    parse_mode="Markdown",
                    reply_markup=_category_keyboard(session),
                )
        return

    note = note_text_from_message(text)
    if note:
        await _save_and_reply_note(update, note)
        return

    await safe_reply(update,
        "No entiendo.\n"
        "• Gasto: `mercadona 44`\n"
        "• Nota: texto libre · `. idea` · 🎤 audio\n"
        "/help — comandos",
        parse_mode="Markdown",
    )


async def unsupported_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foto, documento, sticker, etc.: dar feedback en vez de callar."""
    if not allowed(update):
        return
    await safe_reply(update,
        "Solo entiendo texto y notas de voz por ahora.\n/help — comandos",
    )
