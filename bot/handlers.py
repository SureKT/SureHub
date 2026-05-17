import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from app.config import settings
from app.services.llm import chat


def allowed(update: Update) -> bool:
    return update.effective_user.id in settings.allowed_user_ids


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    await update.message.reply_text("SureHub activo. ¿Qué necesitas?")


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    texto = update.message.text
    await update.message.reply_chat_action("typing")
    respuesta = await asyncio.to_thread(chat, texto)
    await update.message.reply_text(respuesta)
