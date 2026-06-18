from telegram import BotCommand

WELCOME = (
    "*SureHub* — captura rápida\n\n"
    "Escribe sin comando:\n"
    "• *Gasto:* `mercadona 44` · `44.50 cena`\n"
    "• *Nota:* texto libre (varias palabras) o `. idea`\n"
    "• *Voz:* manda un audio 🎤\n\n"
    "/help — comandos"
)

HELP = (
    "*SureHub — comandos*\n\n"
    "*Captura (sin comando)*\n"
    "• Gasto: `descripción cantidad` o `cantidad descripción`\n"
    "• Nota: texto libre · `. nota corta` · 🎤 audio\n\n"
    "*Finanzas*\n"
    "/gastos — últimos gastos (o `/gastos mes`)\n"
    "/mes — resumen del mes y variación vs anterior\n"
    "/borrar — eliminar gasto por id\n"
    "/analisis — análisis IA con confirmación (tiene coste)\n\n"
    "*Inbox*\n"
    "/inbox — procesar notas pendientes (digest)\n\n"
    "/start — mensaje de bienvenida"
)


def bot_commands() -> list[BotCommand]:
    return [
        BotCommand("help", "Lista de comandos"),
        BotCommand("mes", "Resumen del mes"),
        BotCommand("gastos", "Últimos gastos"),
        BotCommand("inbox", "Procesar inbox de notas"),
    ]
