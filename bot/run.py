from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from app.config import settings
from app.database import create_db
import app.models  # noqa: F401 — registra todos los modelos antes de create_db
from bot.handlers import (
    start, message, cmd_gastos, cmd_borrar, callback_borrar, callback_categoria,
    cmd_mes, cmd_categorias, cmd_recuerda, cmd_memoria, cmd_olvidar, cmd_stats
)


def main():
    create_db()
    app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gastos", cmd_gastos))
    app.add_handler(CommandHandler("borrar", cmd_borrar))
    app.add_handler(CommandHandler("mes", cmd_mes))
    app.add_handler(CommandHandler("categorias", cmd_categorias))
    app.add_handler(CommandHandler("recuerda", cmd_recuerda))
    app.add_handler(CommandHandler("memoria", cmd_memoria))
    app.add_handler(CommandHandler("olvidar", cmd_olvidar))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(callback_borrar, pattern="^borrar:"))
    app.add_handler(CallbackQueryHandler(callback_categoria, pattern="^cat:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))
    print("Bot arrancado en modo polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
