from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from app.config import settings
from bot.handlers import start, message


def main():
    app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))
    print("Bot arrancado en modo polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
