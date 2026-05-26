"""
Telegram handlers for the Spotify module.

Commands:
  /spotify_auth     → sends the OAuth link
  /spotify_status   → checks connection
  /spotify_analizar → fetches library + Claude analysis (can take 1-2 min)
"""
import asyncio

from telegram import Update
from telegram.ext import ContextTypes

from app.config import settings
from app.modules.spotify.analyzer import analyze_library
from app.modules.spotify.library import fetch_library
from app.modules.spotify.service import spotify_service


def _allowed(update: Update) -> bool:
    return update.effective_user.id in settings.allowed_user_ids


# ── /spotify_auth ─────────────────────────────────────────────────────────────

async def cmd_spotify_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update):
        return
    user_id = update.effective_user.id
    auth_url = spotify_service.get_auth_url(user_id)
    await update.message.reply_text(
        "🎵 *Conecta tu cuenta de Spotify*\n\n"
        f"Abre este enlace y autoriza el acceso:\n{auth_url}\n\n"
        "Después vuelve aquí y usa /spotify\\_analizar",
        parse_mode="Markdown",
    )


# ── /spotify_status ───────────────────────────────────────────────────────────

async def cmd_spotify_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update):
        return
    user_id = update.effective_user.id
    token_record = spotify_service.get_db_token(user_id)
    if not token_record:
        await update.message.reply_text(
            "❌ No conectado a Spotify.\nUsa /spotify\\_auth para empezar.",
            parse_mode="Markdown",
        )
        return
    access_token = await spotify_service.get_valid_token(user_id)
    if access_token:
        await update.message.reply_text(
            f"✅ Spotify conectado como *{token_record.spotify_display_name}*",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "⚠️ Token expirado y no se pudo renovar.\nUsa /spotify\\_auth de nuevo.",
            parse_mode="Markdown",
        )


# ── /spotify_analizar ─────────────────────────────────────────────────────────

async def cmd_spotify_analizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update):
        return
    user_id = update.effective_user.id

    # Check auth
    if not spotify_service.get_db_token(user_id):
        await update.message.reply_text(
            "❌ No conectado. Usa /spotify\\_auth primero.", parse_mode="Markdown"
        )
        return

    await update.message.reply_text(
        "🎵 Descargando tu biblioteca de Spotify...\n"
        "Esto puede tardar 1-2 minutos según el tamaño. ☕"
    )

    try:
        result = await fetch_library(user_id)
        if result is None:
            await update.message.reply_text(
                "❌ Token inválido. Usa /spotify\\_auth de nuevo.", parse_mode="Markdown"
            )
            return

        liked_tracks, playlists, user = result

        await update.message.reply_text(
            f"📊 {len(liked_tracks)} canciones descargadas. Analizando con IA..."
        )

        stats, analysis = await asyncio.to_thread(
            analyze_library, liked_tracks, playlists
        )

        # ── Summary card ──────────────────────────────────────────────────────
        top_genres_text = "\n".join(
            f"  • {g}: {c}" for g, c in stats["top_genres"][:6]
        )
        summary = (
            f"📊 *Resumen — {user.get('display_name', 'tu biblioteca')}*\n\n"
            f"🎵 Liked songs: `{stats['total_liked']}`\n"
            f"📂 Playlists propias: `{stats['total_playlists']}`\n"
            f"📦 Sin organizar: `{stats['unorganized_count']}`\n\n"
            f"⚡ Energía media: `{stats['avg_energy']}`\n"
            f"😊 Positividad media: `{stats['avg_valence']}`\n"
            f"💃 Bailabilidad media: `{stats['avg_danceability']}`\n\n"
            f"🎸 *Top géneros:*\n{top_genres_text}"
        )
        await update.message.reply_text(summary, parse_mode="Markdown")

        # ── Analysis (split at 4000 chars to respect Telegram limit) ─────────
        for i in range(0, len(analysis), 4000):
            await update.message.reply_text(analysis[i : i + 4000])

    except Exception as exc:
        await update.message.reply_text(f"❌ Error inesperado: {exc}")
