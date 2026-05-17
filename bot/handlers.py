import asyncio
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.config import settings
from app.database import get_session
from app.services.llm import chat
from app.modules.finanzas.models import Gasto, Categoria
from app.modules.finanzas.parser import parsear_gasto
from app.modules.finanzas.service import (
    registrar_gasto, ultimos_gastos, total_mes_global,
    resumen_mes, buscar_categoria, listar_categorias, get_gastos_filtrados,
    generar_recurrentes,
)
from app.modules.memoria.service import guardar_memoria, listar_memorias, borrar_memoria, construir_contexto

MESES_ES = ["enero","febrero","marzo","abril","mayo","junio",
            "julio","agosto","septiembre","octubre","noviembre","diciembre"]


def allowed(update: Update) -> bool:
    return update.effective_user.id in settings.allowed_user_ids


def _barra(total: float, estimacion: float) -> str:
    if estimacion <= 0:
        return ""
    pct = min(total / estimacion, 1.0)
    filled = round(pct * 8)
    return f" `{'█' * filled}{'░' * (8 - filled)}`"


def _construir_contexto_finanzas(session) -> str:
    ahora = datetime.now(timezone.utc)
    total = total_mes_global(session)
    resumen = resumen_mes(session)
    if not resumen and total == 0:
        return ""
    mes_nombre = MESES_ES[ahora.month - 1]
    lineas = [f"Gastos {mes_nombre} {ahora.year} (datos reales):"]
    lineas.append(f"- Total: {total:.2f}€")
    for r in sorted(resumen, key=lambda x: x["total"], reverse=True):
        if r["total"] > 0:
            est = f"/{r['estimacion']:.0f}€" if r["estimacion"] > 0 else ""
            alerta = " [SOBRE PRESUPUESTO]" if r["alerta"] else ""
            lineas.append(f"- {r['nombre']}: {r['total']:.2f}€{est}{alerta}")
    return "\n".join(lineas)


def _categoria_keyboard(session) -> InlineKeyboardMarkup:
    cats = listar_categorias(session)[:8]
    buttons = [InlineKeyboardButton(c.nombre, callback_data=f"cat:{c.id}") for c in cats]
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton("Sin categoría", callback_data="cat:0")])
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    await update.message.reply_text(
        "*SureHub*\n\n"
        "*Gastos*\n"
        "• Texto libre: `mercadona 44`, `44.50 cena`, `farmacia 12`\n"
        "• /gastos — últimos 10\n"
        "• /gastos mes — filtrar mes actual\n"
        "• /borrar <id> — eliminar gasto\n"
        "• /mes — resumen del mes\n"
        "• /stats — resumen rápido\n"
        "• /generar — generar recurrentes del mes\n"
        "• /analisis — análisis IA de tus finanzas\n"
        "• /categorias\n\n"
        "*Memoria*\n"
        "• /recuerda <hecho>\n"
        "• /memoria\n"
        "• /olvidar <id>\n\n"
        "O escríbeme.",
        parse_mode="Markdown"
    )


async def cmd_gastos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    session = next(get_session())
    filtrar_mes = context.args and context.args[0].lower() in ("mes", "month")

    if filtrar_mes:
        ahora = datetime.now(timezone.utc)
        gastos_raw, total_count = get_gastos_filtrados(
            session, anio=ahora.year, mes=ahora.month,
            page=1, per_page=15, orden="fecha", asc=False
        )
    else:
        gastos_raw = ultimos_gastos(session, 10)
        total_count = len(gastos_raw)

    if not gastos_raw:
        await update.message.reply_text("Sin gastos registrados.")
        return

    lineas = []
    for g, cat in gastos_raw:
        cat_nombre = cat.nombre if cat else "—"
        desc = f" {g.descripcion}" if g.descripcion else ""
        fecha = g.fecha.strftime("%d/%m") if g.fecha else ""
        lineas.append(f"`{g.id:4d}` {fecha}  *{g.cantidad:.2f}€*  {cat_nombre}{desc}")

    header = f"Mes actual ({total_count} gastos):" if filtrar_mes else "Últimos gastos:"
    await update.message.reply_text(header + "\n" + "\n".join(lineas), parse_mode="Markdown")


async def cmd_borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    if not context.args:
        await update.message.reply_text("Uso: /borrar <id>")
        return
    try:
        gasto_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID debe ser un número.")
        return

    session = next(get_session())
    gasto = session.get(Gasto, gasto_id)
    if not gasto:
        await update.message.reply_text(f"No existe el gasto #{gasto_id}.")
        return

    cat = session.get(Categoria, gasto.categoria_id) if gasto.categoria_id else None
    cat_nombre = cat.nombre if cat else "sin categoría"
    desc = f" — {gasto.descripcion}" if gasto.descripcion else ""

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✓ Confirmar", callback_data=f"borrar:{gasto_id}"),
        InlineKeyboardButton("✕ Cancelar", callback_data="borrar:cancel"),
    ]])
    await update.message.reply_text(
        f"Borrar gasto #{gasto_id}?\n`{gasto.cantidad:.2f}€`  {cat_nombre}{desc}",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def callback_borrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "borrar:cancel":
        await query.edit_message_text("Cancelado.")
        return

    gasto_id = int(query.data.split(":")[1])
    session = next(get_session())
    gasto = session.get(Gasto, gasto_id)
    if not gasto:
        await query.edit_message_text("No encontrado.")
        return
    session.delete(gasto)
    session.commit()
    await query.edit_message_text(f"✓ Gasto #{gasto_id} eliminado.")


async def callback_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pending = context.user_data.get("pending_gasto")
    if not pending:
        await query.edit_message_text("Sin gasto pendiente.")
        return

    cat_id_str = query.data.split(":")[1]
    cat_id = int(cat_id_str) if cat_id_str != "0" else None

    session = next(get_session())
    g = registrar_gasto(session, pending["cantidad"], cat_id, pending["descripcion"])

    cat = session.get(Categoria, cat_id) if cat_id else None
    cat_nombre = cat.nombre if cat else "sin categoría"
    context.user_data.pop("pending_gasto", None)

    await query.edit_message_text(
        f"✓ *{pending['descripcion']}* — {pending['cantidad']:.2f}€ ({cat_nombre})",
        parse_mode="Markdown"
    )


async def cmd_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    session = next(get_session())
    resumen = resumen_mes(session)
    total = total_mes_global(session)

    if not resumen:
        await update.message.reply_text("Sin categorías. Configúralas desde el dashboard.")
        return

    variable = [r for r in resumen if r["tipo"] == "variable" and (r["total"] > 0 or r["estimacion"] > 0)]
    fijo = [r for r in resumen if r["tipo"] == "fijo" and (r["total"] > 0 or r["estimacion"] > 0)]

    lineas = []
    for seccion, items in [("Variable", variable), ("Fijo", fijo)]:
        if not items:
            continue
        lineas.append(f"*{seccion}*")
        for r in items:
            alerta = " ⚠" if r["alerta"] else ""
            barra = _barra(r["total"], r["estimacion"])
            est = f"/{r['estimacion']:.0f}€" if r["estimacion"] > 0 else ""
            lineas.append(f"  {r['nombre']}: {r['total']:.0f}€{est}{alerta}{barra}")

    lineas.append(f"\n*Total: {total:.2f}€*")
    await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")


async def cmd_categorias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    session = next(get_session())
    cats = listar_categorias(session)
    if not cats:
        await update.message.reply_text("Sin categorías.")
        return
    variable = [c for c in cats if c.tipo == "variable"]
    fijo = [c for c in cats if c.tipo == "fijo"]
    lineas = ["*Variable*"] + [f"  {c.nombre}" + (f" — {c.estimacion_mensual:.0f}€/mes" if c.estimacion_mensual > 0 else "") for c in variable]
    if fijo:
        lineas += ["\n*Fijo*"] + [f"  {c.nombre}" + (f" — {c.estimacion_mensual:.0f}€/mes" if c.estimacion_mensual > 0 else "") for c in fijo]
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
    await update.message.reply_text(f"✓ Guardado (#{m.id})")


async def cmd_memoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    session = next(get_session())
    memorias = listar_memorias(session)
    if not memorias:
        await update.message.reply_text("Sin memoria guardada.")
        return
    lineas = [f"`{m.id}` {m.hecho}" for m in memorias]
    await update.message.reply_text("*Memoria:*\n" + "\n".join(lineas), parse_mode="Markdown")


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


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    session = next(get_session())
    ahora = datetime.now(timezone.utc)
    total = total_mes_global(session)
    mes_ant = ahora.month - 1 or 12
    anio_ant = ahora.year if ahora.month > 1 else ahora.year - 1
    total_ant = total_mes_global(session, anio_ant, mes_ant)
    resumen = resumen_mes(session)
    alertas = [r for r in resumen if r["alerta"]]
    activos = [r for r in resumen if r["total"] > 0]
    top = max(activos, key=lambda r: r["total"]) if activos else None

    mes_nombre = MESES_ES[ahora.month - 1].capitalize()
    lineas = [f"*{mes_nombre} {ahora.year}*"]

    if total_ant > 0:
        pct = ((total - total_ant) / total_ant) * 100
        signo = "+" if pct >= 0 else ""
        flecha = "▲" if pct > 5 else ("▼" if pct < -5 else "→")
        lineas.append(f"Total: *{total:.2f}€*  {flecha} {signo}{pct:.0f}% vs {MESES_ES[mes_ant-1]}")
    else:
        lineas.append(f"Total: *{total:.2f}€*")

    if top:
        pct_top = (top['total'] / total * 100) if total > 0 else 0
        lineas.append(f"Top: {top['nombre']} — {top['total']:.0f}€ ({pct_top:.0f}%)")

    if alertas:
        cats = ", ".join(a["nombre"] for a in alertas)
        lineas.append(f"⚠ Sobre presupuesto: {cats}")
    else:
        lineas.append("Todos los presupuestos OK")

    await update.message.reply_text("\n".join(lineas), parse_mode="Markdown")


async def cmd_analisis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    pregunta = " ".join(context.args).strip() if context.args else ""
    if not pregunta:
        pregunta = "Analiza mis gastos de este mes. ¿En qué destaco positiva o negativamente? ¿Algún consejo concreto?"
    session = next(get_session())
    contexto_memoria = construir_contexto(session)
    contexto_finanzas = _construir_contexto_finanzas(session)
    await update.message.reply_chat_action("typing")
    respuesta = await asyncio.to_thread(chat, pregunta, contexto_memoria, contexto_finanzas)
    await update.message.reply_text(respuesta, parse_mode="Markdown")


async def cmd_generar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    session = next(get_session())
    ahora = datetime.now(timezone.utc)
    result = generar_recurrentes(session, ahora.year, ahora.month)
    total = result["total"]
    if total == 0:
        await update.message.reply_text("Todos los recurrentes ya generados este mes.")
        return
    lineas = [f"✓ {g['nombre']} — {g['cantidad']:.2f}€" for g in result["generados"]]
    await update.message.reply_text(
        f"*{total} gasto{'s' if total > 1 else ''} generado{'s' if total > 1 else ''}:*\n" + "\n".join(lineas),
        parse_mode="Markdown"
    )


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    texto = update.message.text

    gasto = parsear_gasto(texto)
    if gasto:
        session = next(get_session())
        cat = buscar_categoria(session, gasto.categoria_hint) if gasto.categoria_hint else None

        if cat:
            registrar_gasto(session, gasto.cantidad, cat.id, gasto.descripcion)
            await update.message.reply_text(
                f"✓ *{gasto.descripcion}* — {gasto.cantidad:.2f}€ ({cat.nombre})",
                parse_mode="Markdown"
            )
        else:
            # No category matched — ask with inline keyboard
            context.user_data["pending_gasto"] = {
                "descripcion": gasto.descripcion,
                "cantidad": gasto.cantidad,
            }
            await update.message.reply_text(
                f"*{gasto.descripcion}* — {gasto.cantidad:.2f}€\n¿Categoría?",
                parse_mode="Markdown",
                reply_markup=_categoria_keyboard(session),
            )
        return

    await update.message.reply_text(
        "No entiendo. Escribe un gasto (ej: `mercadona 44`, `cena 32.50`) o usa /help.",
        parse_mode="Markdown"
    )
