"""
FastAPI router for the Spotify module.

Endpoints:
  GET  /spotify/auth?telegram_user_id=...   → redirect to Spotify OAuth
  GET  /spotify/callback?code=...&state=... → handle OAuth callback
  GET  /spotify/status/{telegram_user_id}   → check auth status
  POST /spotify/analyze/{telegram_user_id}  → fetch library + Claude analysis
"""
import asyncio

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.modules.spotify.analyzer import analyze_library
from app.modules.spotify.library import fetch_library
from app.modules.spotify.service import spotify_service

router = APIRouter(prefix="/spotify", tags=["spotify"])


# ── OAuth ─────────────────────────────────────────────────────────────────────

@router.get("/auth")
async def start_auth(telegram_user_id: int = Query(..., description="Telegram user ID")):
    """Redirect the user to the Spotify authorization page."""
    url = spotify_service.get_auth_url(telegram_user_id)
    return RedirectResponse(url)


@router.get("/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
):
    """Handle Spotify OAuth callback and persist the tokens."""
    try:
        telegram_user_id = int(state)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid state parameter.")

    await spotify_service.exchange_code(code, telegram_user_id)

    return HTMLResponse("""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>Spotify conectado</title>
<style>
  body { font-family: sans-serif; text-align: center; padding: 60px; background: #121212; color: #fff; }
  h2   { color: #1DB954; }
  code { background: #282828; padding: 2px 6px; border-radius: 4px; }
</style></head>
<body>
  <h2>✅ Spotify conectado correctamente</h2>
  <p>Puedes cerrar esta ventana y volver a Telegram.</p>
  <p>Usa <code>/spotify_analizar</code> para analizar tu biblioteca.</p>
</body>
</html>
""")


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status/{telegram_user_id}")
async def auth_status(telegram_user_id: int):
    token_record = spotify_service.get_db_token(telegram_user_id)
    if not token_record:
        return {"authenticated": False, "spotify_user": None}
    # Try to get a valid (possibly refreshed) token
    access_token = await spotify_service.get_valid_token(telegram_user_id)
    return {
        "authenticated": bool(access_token),
        "spotify_user": token_record.spotify_display_name,
    }


# ── Analyze ───────────────────────────────────────────────────────────────────

@router.post("/analyze/{telegram_user_id}")
async def analyze(telegram_user_id: int):
    """Fetch the user's full Spotify library and return a Claude analysis."""
    result = await fetch_library(telegram_user_id)
    if result is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with Spotify. Call GET /spotify/auth first.",
        )

    liked_tracks, playlists, user = result

    stats, analysis = await asyncio.to_thread(analyze_library, liked_tracks, playlists)

    return {
        "spotify_user": user.get("display_name"),
        "stats": {
            **stats,
            "top_genres": stats["top_genres"][:15],  # trim for JSON response
        },
        "analysis": analysis,
    }
