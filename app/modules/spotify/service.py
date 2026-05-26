"""
SpotifyService — OAuth 2.0 + Spotify Web API via httpx (no extra deps).
Stores tokens in the SureHub database.
"""
import asyncio
import base64
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
from sqlmodel import Session, select

from app.config import settings
from app.database import engine
from app.modules.spotify.models import SpotifyToken


class SpotifyService:
    BASE = "https://api.spotify.com/v1"
    AUTH_URL = "https://accounts.spotify.com/authorize"
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    SCOPES = (
        "user-library-read "
        "playlist-read-private "
        "playlist-read-collaborative "
        "playlist-modify-private "
        "playlist-modify-public "
        "user-top-read"
    )

    # ── Auth URL ──────────────────────────────────────────────────────────────

    def get_auth_url(self, telegram_user_id: int) -> str:
        params = {
            "client_id": settings.SPOTIFY_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
            "scope": self.SCOPES,
            "state": str(telegram_user_id),
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    # ── Token exchange & refresh ──────────────────────────────────────────────

    def _basic_auth(self) -> str:
        creds = f"{settings.SPOTIFY_CLIENT_ID}:{settings.SPOTIFY_CLIENT_SECRET}"
        return base64.b64encode(creds.encode()).decode()

    async def exchange_code(self, code: str, telegram_user_id: int) -> SpotifyToken:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
                },
                headers={"Authorization": f"Basic {self._basic_auth()}"},
            )
            resp.raise_for_status()
            data = resp.json()

        access_token = data["access_token"]
        user = await self.get_user_profile(access_token)
        expires_at = datetime.utcnow() + timedelta(seconds=data["expires_in"])

        with Session(engine) as session:
            existing = session.exec(
                select(SpotifyToken).where(
                    SpotifyToken.telegram_user_id == telegram_user_id
                )
            ).first()

            if existing:
                existing.access_token = access_token
                existing.refresh_token = data["refresh_token"]
                existing.expires_at = expires_at
                existing.spotify_user_id = user["id"]
                existing.spotify_display_name = user.get("display_name", "")
                existing.scope = data.get("scope", "")
                existing.updated_at = datetime.utcnow()
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing

            token = SpotifyToken(
                telegram_user_id=telegram_user_id,
                spotify_user_id=user["id"],
                spotify_display_name=user.get("display_name", ""),
                access_token=access_token,
                refresh_token=data["refresh_token"],
                expires_at=expires_at,
                scope=data.get("scope", ""),
            )
            session.add(token)
            session.commit()
            session.refresh(token)
            return token

    async def _refresh_token(self, token: SpotifyToken) -> SpotifyToken:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": token.refresh_token,
                },
                headers={"Authorization": f"Basic {self._basic_auth()}"},
            )
            resp.raise_for_status()
            data = resp.json()

        with Session(engine) as session:
            db_token = session.get(SpotifyToken, token.id)
            db_token.access_token = data["access_token"]
            db_token.expires_at = datetime.utcnow() + timedelta(seconds=data["expires_in"])
            if "refresh_token" in data:
                db_token.refresh_token = data["refresh_token"]
            db_token.updated_at = datetime.utcnow()
            session.add(db_token)
            session.commit()
            session.refresh(db_token)
            return db_token

    async def get_valid_token(self, telegram_user_id: int) -> Optional[str]:
        with Session(engine) as session:
            token = session.exec(
                select(SpotifyToken).where(
                    SpotifyToken.telegram_user_id == telegram_user_id
                )
            ).first()

        if not token:
            return None

        if datetime.utcnow() >= token.expires_at - timedelta(minutes=5):
            token = await self._refresh_token(token)

        return token.access_token

    def get_db_token(self, telegram_user_id: int) -> Optional[SpotifyToken]:
        with Session(engine) as session:
            return session.exec(
                select(SpotifyToken).where(
                    SpotifyToken.telegram_user_id == telegram_user_id
                )
            ).first()

    # ── API helpers ───────────────────────────────────────────────────────────

    async def _get(self, access_token: str, path: str, params: dict = None) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE}{path}",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()

    async def _post(self, access_token: str, path: str, payload: dict) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE}{path}",
                json=payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()

    # ── Spotify API calls ─────────────────────────────────────────────────────

    async def get_user_profile(self, access_token: str) -> dict:
        return await self._get(access_token, "/me")

    async def get_liked_songs(self, access_token: str) -> list:
        items, offset = [], 0
        while True:
            data = await self._get(
                access_token, "/me/tracks", {"limit": 50, "offset": offset}
            )
            items.extend(data["items"])
            if not data["next"]:
                break
            offset += 50
            await asyncio.sleep(0.1)
        return items

    async def get_own_playlists(self, access_token: str, spotify_user_id: str) -> list:
        playlists, offset = [], 0
        while True:
            data = await self._get(
                access_token, "/me/playlists", {"limit": 50, "offset": offset}
            )
            playlists.extend(data["items"])
            if not data["next"]:
                break
            offset += 50
        return [p for p in playlists if p["owner"]["id"] == spotify_user_id]

    async def get_playlist_tracks(self, access_token: str, playlist_id: str) -> list:
        items, offset = [], 0
        while True:
            data = await self._get(
                access_token,
                f"/playlists/{playlist_id}/tracks",
                {
                    "limit": 100,
                    "offset": offset,
                    "fields": "items(track(id,name,artists)),next",
                },
            )
            items.extend(data["items"])
            if not data["next"]:
                break
            offset += 100
            await asyncio.sleep(0.05)
        return [t["track"] for t in items if t["track"] and t["track"].get("id")]

    async def get_audio_features(self, access_token: str, track_ids: list) -> dict:
        features = {}
        for i in range(0, len(track_ids), 100):
            batch = track_ids[i : i + 100]
            data = await self._get(
                access_token, "/audio-features", {"ids": ",".join(batch)}
            )
            for f in data.get("audio_features", []):
                if f:
                    features[f["id"]] = f
            await asyncio.sleep(0.1)
        return features

    async def get_artist_genres(self, access_token: str, artist_ids: list) -> dict:
        genres = {}
        unique_ids = list(set(filter(None, artist_ids)))
        for i in range(0, len(unique_ids), 50):
            batch = unique_ids[i : i + 50]
            data = await self._get(
                access_token, "/artists", {"ids": ",".join(batch)}
            )
            for a in data.get("artists", []):
                if a:
                    genres[a["id"]] = a.get("genres", [])
            await asyncio.sleep(0.1)
        return genres

    async def create_playlist(
        self,
        access_token: str,
        spotify_user_id: str,
        name: str,
        description: str,
        track_ids: list,
    ) -> dict:
        playlist = await self._post(
            access_token,
            f"/users/{spotify_user_id}/playlists",
            {"name": name, "description": description, "public": False},
        )
        await self.add_tracks_to_playlist(access_token, playlist["id"], track_ids)
        return playlist

    async def add_tracks_to_playlist(
        self, access_token: str, playlist_id: str, track_ids: list
    ):
        async with httpx.AsyncClient() as client:
            for i in range(0, len(track_ids), 100):
                uris = [f"spotify:track:{tid}" for tid in track_ids[i : i + 100]]
                resp = await client.post(
                    f"{self.BASE}/playlists/{playlist_id}/tracks",
                    json={"uris": uris},
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )
                resp.raise_for_status()


spotify_service = SpotifyService()
