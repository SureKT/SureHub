from telegram import BotCommand

WELCOME = (
    "*SureHub* — captura rápida\n\n"
    "Escribe sin comando:\n"
    "• *Gasto:* `mercadona 44` · `44.50 cena`\n"
    "• *Nota:* texto libre (varias palabras) o `. idea`\n"
    "• *Voz:* manda un audio 🎤\n\n"
    "/help — lista completa de comandos"
)

HELP = (
    "*SureHub — comandos*\n\n"
    "*Captura (sin comando)*\n"
    "• Gasto: `descripción cantidad` o `cantidad descripción`\n"
    "• Nota: texto libre · `. nota corta` · /nota texto · 🎤 audio\n\n"
    "*Finanzas*\n"
    "/gastos — últimos 10 gastos\n"
    "/gastos mes — gastos del mes actual\n"
    "/borrar — eliminar gasto por id\n"
    "/mes — resumen por categoría\n"
    "/stats — total y variación vs mes anterior\n"
    "/generar — crear gastos recurrentes del mes\n"
    "/analisis — análisis IA (opcional: pregunta)\n"
    "/categorias — listar categorías\n\n"
    "*Notas (Obsidian)*\n"
    "/nota — guardar nota con tags IA\n"
    "/note — alias de /nota\n\n"
    "*Inbox*\n"
    "/inbox — procesar notas pendientes (digest)\n\n"
    "*Memoria del bot*\n"
    "/recuerda — guardar un hecho\n"
    "/memoria — ver memoria guardada\n"
    "/olvidar — borrar por id\n\n"
    "/start — mensaje de bienvenida"
)


def bot_commands() -> list[BotCommand]:
    return [
        BotCommand("help", "Lista de comandos"),
        BotCommand("gastos", "Últimos gastos"),
        BotCommand("mes", "Resumen del mes"),
        BotCommand("stats", "Estadísticas rápidas"),
        BotCommand("nota", "Guardar nota en Obsidian"),
        BotCommand("inbox", "Procesar inbox de notas"),
        BotCommand("recuerda", "Guardar en memoria del bot"),
        BotCommand("memoria", "Ver memoria"),
        BotCommand("analisis", "Análisis IA de finanzas"),
        BotCommand("generar", "Gastos recurrentes del mes"),
        BotCommand("categorias", "Listar categorías"),
        BotCommand("borrar", "Eliminar gasto"),
    ]
