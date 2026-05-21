"""
Fetches and enriches a user's full Spotify library.
Shared between the FastAPI router and the Telegram bot handler.
"""
import asyncio
from typing import Optional

from app.modules.spotify.service import spotify_service


async def fetch_library(telegram_user_id: int) -> Optional[tuple[list, list, dict]]:
    """
    Returns (liked_tracks, playlists, user_profile) or None if not authenticated.

    liked_tracks: list of dicts with id, name, artist, genres, audio features.
    playlists:    list of dicts with id, name, description, track_ids.
    user_profile: raw /me response from Spotify.
    """
    access_token = await spotify_service.get_valid_token(telegram_user_id)
    if not access_token:
        return None

    user = await spotify_service.get_user_profile(access_token)

    # ── Liked songs ───────────────────────────────────────────────────────────
    liked_raw = await spotify_service.get_liked_songs(access_token)

    liked_tracks = []
    all_artist_ids = []
    for item in liked_raw:
        t = item["track"]
        if not t or not t.get("id"):
            continue
        artist_id = t["artists"][0]["id"] if t.get("artists") else None
        if artist_id:
            all_artist_ids.append(artist_id)
        liked_tracks.append(
            {
                "id": t["id"],
                "name": t["name"],
                "artist": t["artists"][0]["name"] if t.get("artists") else "Unknown",
                "artist_id": artist_id,
                "album": t.get("album", {}).get("name", ""),
                # enriched below
                "energy": None,
                "valence": None,
                "danceability": None,
                "tempo": None,
                "acousticness": None,
                "instrumentalness": None,
                "genres": [],
            }
        )

    # ── Enrich with audio features + genres (parallel) ───────────────────────
    track_ids = [t["id"] for t in liked_tracks]
    audio_features_task = asyncio.create_task(
        spotify_service.get_audio_features(access_token, track_ids)
    )
    artist_genres_task = asyncio.create_task(
        spotify_service.get_artist_genres(access_token, all_artist_ids)
    )
    audio_features, artist_genres = await asyncio.gather(
        audio_features_task, artist_genres_task
    )

    for t in liked_tracks:
        feat = audio_features.get(t["id"], {})
        t["energy"] = feat.get("energy")
        t["valence"] = feat.get("valence")
        t["danceability"] = feat.get("danceability")
        t["tempo"] = feat.get("tempo")
        t["acousticness"] = feat.get("acousticness")
        t["instrumentalness"] = feat.get("instrumentalness")
        t["genres"] = artist_genres.get(t["artist_id"] or "", [])

    # ── Playlists + their track IDs ───────────────────────────────────────────
    playlists_raw = await spotify_service.get_own_playlists(
        access_token, user["id"]
    )
    playlists = []
    for p in playlists_raw:
        tracks = await spotify_service.get_playlist_tracks(access_token, p["id"])
        playlists.append(
            {
                "id": p["id"],
                "name": p["name"],
                "description": p.get("description", ""),
                "track_ids": [t["id"] for t in tracks],
            }
        )

    return liked_tracks, playlists, user
