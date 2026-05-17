import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from app.config import settings
from app.database import get_session
from app.services.llm import chat
from app.modules.finanzas.parser import parsear_gasto
from app.modules.finanzas.service import (
    registrar_gasto, ultimos_gastos, total_mes_global,
    resumen_mes, buscar_categoria, listar_categorias
)
from app.modules.memoria.service import guardar_memoria, listar_memorias, borrar_memoria, construir_contexto


def allowed(update: Update) -> bool:
    return update.effective_user.id in settings.allowed_user_ids


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    await update.message.reply_text(
        "SureHub activo.\n\n"
        "*Finanzas*\n"
        "• Registrar gasto: `mercadona 44` o `44 mercadona`\n"
        "• /gastos — últimos gastos\n"
        "• /mes — resumen del mes\n"
        "• /categorias — lista de categorías\n\n"
        "*Memoria*\n"
        "• /recuerda <hecho>\n"
        "• /memoria\n"
        "• /olvidar <id>\n\n"
        "O habla conmigo.",
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
    lineas = []
    for g, cat in gastos:
        cat_nombre = cat.nombre if cat else "sin categoría"
        desc = f" — {g.descripcion}" if g.descripcion else ""
        lineas.append(f"• {cat_nombre}{desc}: {g.cantidad:.2f}€")
    await update.message.reply_text("Últimos gastos:\n" + "\n".join(lineas))


async def cmd_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    session = next(get_session())
    resumen = resumen_mes(session)
    total = total_mes_global(session)

    if not resumen:
        await update.message.reply_text("Sin categorías definidas. Usa el dashboard para configurarlas.")
        return

    lineas = []
    for r in resumen:
        if r["total"] == 0 and r["estimacion"] == 0:
            continue
        alerta = " ⚠" if r["alerta"] else ""
        lineas.append(f"• {r['nombre']}: {r['total']:.0f}€ / {r['estimacion']:.0f}€{alerta}")

    lineas.append(f"\nTotal: {total:.2f}€")
    await update.message.reply_text("Mes actual:\n" + "\n".join(lineas))


async def cmd_categorias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    session = next(get_session())
    cats = listar_categorias(session)
    if not cats:
        await update.message.reply_text("Sin categorías. Configúralas desde el dashboard.")
        return
    variable = [c for c in cats if c.tipo == "variable"]
    fijo = [c for c in cats if c.tipo == "fijo"]
    lineas = ["*Variable*"] + [f"  {c.nombre} — {c.estimacion_mensual:.0f}€/mes" for c in variable]
    lineas += ["\n*Fijo*"] + [f"  {c.nombre} — {c.estimacion_mensual:.0f}€/mes" for c in fijo]
    await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")


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
    await update.message.reply_text("✓ Olvidado." if ok else "No encontrado.")


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    texto = update.message.text

    gasto = parsear_gasto(texto)
    if gasto:
        session = next(get_session())
        cat = buscar_categoria(session, gasto.categoria_hint) if gasto.categoria_hint else None
        g = registrar_gasto(session, gasto.cantidad, cat.id if cat else None, gasto.descripcion)
        cat_nombre = cat.nombre if cat else "sin categoría"
        await update.message.reply_text(f"✓ {gasto.descripcion} — {gasto.cantidad:.2f}€ ({cat_nombre})")
        return

    session = next(get_session())
    contexto = construir_contexto(session)
    await update.message.reply_chat_action("typing")
    respuesta = await asyncio.to_thread(chat, texto, contexto)
    await update.message.reply_text(respuesta, parse_mode="Markdown")
