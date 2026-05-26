from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from app.config import settings
from app.database import create_db
import app.models  # noqa: F401 — registers all models before create_db
from bot.handlers import (
    start, message, cmd_gastos, cmd_borrar, callback_borrar, callback_categoria,
    cmd_mes, cmd_categorias, cmd_recuerda, cmd_memoria, cmd_olvidar, cmd_stats,
    cmd_generar, cmd_analisis,
)
from app.modules.spotify.bot import (
    cmd_spotify_auth,
    cmd_spotify_status,
    cmd_spotify_analizar,
)


def main():
    create_db()
    app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Core
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gastos", cmd_gastos))
    app.add_handler(CommandHandler("borrar", cmd_borrar))
    app.add_handler(CommandHandler("mes", cmd_mes))
    app.add_handler(CommandHandler("categorias", cmd_categorias))
    app.add_handler(CommandHandler("recuerda", cmd_recuerda))
    app.add_handler(CommandHandler("memoria", cmd_memoria))
    app.add_handler(CommandHandler("olvidar", cmd_olvidar))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("generar", cmd_generar))
    app.add_handler(CommandHandler("analisis", cmd_analisis))
    app.add_handler(CallbackQueryHandler(callback_borrar, pattern="^borrar:"))
    app.add_handler(CallbackQueryHandler(callback_categoria, pattern="^cat:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))

    # Spotify
    app.add_handler(CommandHandler("spotify_auth", cmd_spotify_auth))
    app.add_handler(CommandHandler("spotify_status", cmd_spotify_status))
    app.add_handler(CommandHandler("spotify_analizar", cmd_spotify_analizar))

    print("Bot arrancado en modo polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
