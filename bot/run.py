from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from app.config import settings
from app.database import create_db
import app.models  # noqa: F401 — registra todos los modelos antes de create_db
from bot.handlers import start, message, cmd_gastos, cmd_mes, cmd_categorias


def main():
    create_db()
    app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gastos", cmd_gastos))
    app.add_handler(CommandHandler("mes", cmd_mes))
    app.add_handler(CommandHandler("categorias", cmd_categorias))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))
    print("Bot arrancado en modo polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
