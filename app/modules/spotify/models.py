from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class SpotifyToken(SQLModel, table=True):
    __tablename__ = "spotify_tokens"

    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_user_id: int = Field(index=True, unique=True)
    spotify_user_id: str
    spotify_display_name: str = ""
    access_token: str
    refresh_token: str
    expires_at: datetime
    scope: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
