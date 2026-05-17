import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from app.config import settings
from app.database import get_session
from app.services.llm import chat
from app.modules.finanzas.parser import parsear_gasto
from app.modules.finanzas.service import registrar_gasto, total_mes, ultimos_gastos, gastos_por_categoria
from app.modules.memoria.service import guardar_memoria, listar_memorias, borrar_memoria, construir_contexto


def allowed(update: Update) -> bool:
    return update.effective_user.id in settings.allowed_user_ids


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    await update.message.reply_text(
        "SureHub activo.\n\n"
        "*Finanzas*\n"
        "• Registrar gasto: `café 2.50`\n"
        "• /gastos — últimos gastos\n"
        "• /mes — total del mes\n"
        "• /categorias — resumen por categoría\n\n"
        "*Memoria*\n"
        "• /recuerda <hecho> — guardar algo\n"
        "• /memoria — ver todo\n"
        "• /olvidar <id> — borrar un hecho\n\n"
        "O simplemente habla conmigo.",
        parse_mode="Markdown"
    )


async def cmd_gastos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    session = next(get_session())
    gastos = ultimos_gastos(session)
    if not gastos:
        await update.message.reply_text("Sin gastos registrados.")
        return
    lineas = [f"• {g.descripcion} — {g.cantidad:.2f}€ ({g.categoria or 'sin categoría'})" for g in gastos]
    await update.message.reply_text("Últimos gastos:\n" + "\n".join(lineas))


async def cmd_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    session = next(get_session())
    total = total_mes(session)
    await update.message.reply_text(f"Total este mes: {total:.2f}€")


async def cmd_categorias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    session = next(get_session())
    cats = gastos_por_categoria(session)
    if not cats:
        await update.message.reply_text("Sin gastos registrados.")
        return
    lineas = [f"• {cat}: {total:.2f}€" for cat, total in sorted(cats.items(), key=lambda x: -x[1])]
    await update.message.reply_text("Por categoría:\n" + "\n".join(lineas))


async def cmd_recuerda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    hecho = " ".join(context.args).strip()
    if not hecho:
        await update.message.reply_text("Uso: /recuerda <hecho>")
        return
    session = next(get_session())
    m = guardar_memoria(session, hecho)
    await update.message.reply_text(f"✓ Guardado (id: {m.id}): {hecho}")


async def cmd_memoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    session = next(get_session())
    memorias = listar_memorias(session)
    if not memorias:
        await update.message.reply_text("Sin memoria guardada.")
        return
    lineas = [f"[{m.id}] {m.hecho}" for m in memorias]
    await update.message.reply_text("Memoria:\n" + "\n".join(lineas))


async def cmd_olvidar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    if not context.args:
        await update.message.reply_text("Uso: /olvidar <id>")
        return
    try:
        id_ = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID debe ser un número.")
        return
    session = next(get_session())
    ok = borrar_memoria(session, id_)
    await update.message.reply_text(f"✓ Olvidado." if ok else "No encontrado.")


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    texto = update.message.text

    gasto = parsear_gasto(texto)
    if gasto:
        session = next(get_session())
        registrar_gasto(session, gasto.descripcion, gasto.cantidad, gasto.categoria)
        cat = f" ({gasto.categoria})" if gasto.categoria else ""
        await update.message.reply_text(f"✓ {gasto.descripcion} — {gasto.cantidad:.2f}€{cat}")
        return

    session = next(get_session())
    contexto = construir_contexto(session)
    await update.message.reply_chat_action("typing")
    respuesta = await asyncio.to_thread(chat, texto, contexto)
    await update.message.reply_text(respuesta, parse_mode="Markdown")
