from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from app.config import settings
from bot.handlers import start, message
from app.modules.spotify.bot import (
    cmd_spotify_auth,
    cmd_spotify_status,
    cmd_spotify_analizar,
)


def main():
    app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Core
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))

    # Spotify
    app.add_handler(CommandHandler("spotify_auth", cmd_spotify_auth))
    app.add_handler(CommandHandler("spotify_status", cmd_spotify_status))
    app.add_handler(CommandHandler("spotify_analizar", cmd_spotify_analizar))

    print("Bot arrancado en modo polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
