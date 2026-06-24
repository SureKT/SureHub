import logging
from datetime import time as dtime
from zoneinfo import ZoneInfo
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from app.config import settings
from app.database import create_db

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    level=logging.INFO,
)
# httpx loguea la URL completa (incluye el token del bot) en INFO → silenciar.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("surehub.bot")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Error en handler", exc_info=context.error)
import app.models  # noqa: F401 — registers all models before create_db
from bot.help_text import bot_commands
from bot.handlers import (
    start, cmd_help, message, voice_message, unsupported_message, cmd_gastos, cmd_gastosid, cmd_borrar,
    callback_borrar, callback_categoria, callback_analisis, cmd_mes, cmd_categorias, cmd_analisis, cmd_nota,
)
from bot.inbox_handlers import cmd_inbox, callback_inbox, inbox_digest_job


async def post_init(app):
    await app.bot.set_my_commands(bot_commands())


def main():
    create_db()
    app = (
        ApplicationBuilder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Core
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("ayuda", cmd_help))
    app.add_handler(CommandHandler("comandos", cmd_help))
    app.add_handler(CommandHandler("gastos", cmd_gastos))
    app.add_handler(CommandHandler("gastosid", cmd_gastosid))
    app.add_handler(CommandHandler("borrar", cmd_borrar))
    app.add_handler(CommandHandler("mes", cmd_mes))
    app.add_handler(CommandHandler("categorias", cmd_categorias))
    app.add_handler(CommandHandler("analisis", cmd_analisis))
    app.add_handler(CallbackQueryHandler(callback_analisis, pattern="^analisis:"))
    app.add_handler(CommandHandler("nota", cmd_nota))
    app.add_handler(CommandHandler("note", cmd_nota))
    app.add_handler(CommandHandler("inbox", cmd_inbox))
    app.add_handler(CallbackQueryHandler(callback_borrar, pattern="^borrar:"))
    app.add_handler(CallbackQueryHandler(callback_categoria, pattern="^cat:"))
    app.add_handler(CallbackQueryHandler(callback_inbox, pattern="^inbox:"))
    app.add_handler(MessageHandler(filters.VOICE, voice_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))
    # Catch-all para media no soportada (foto, documento, sticker…): registrado al
    # final del grupo, solo captura lo que no casó con text/voice/comandos.
    app.add_handler(MessageHandler(
        ~filters.TEXT & ~filters.VOICE & ~filters.COMMAND & ~filters.StatusUpdate.ALL,
        unsupported_message,
    ))

    app.add_error_handler(on_error)

    app.job_queue.run_daily(
        inbox_digest_job,
        time=dtime(hour=settings.INBOX_DIGEST_HOUR, tzinfo=ZoneInfo(settings.TIMEZONE)),
    )

    logger.info("Bot arrancado en modo polling...")
    # allowed_updates explícito: Telegram persiste el set entre llamadas a getUpdates;
    # sin esto hereda un set previo que excluía callback_query (clicks en botones).
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
