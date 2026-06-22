from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class GoogleToken(SQLModel, table=True):
    __tablename__ = "google_tokens"

    id: Optional[int] = Field(default=None, primary_key=True)
    access_token: str
    refresh_token: str
    token_expiry: Optional[datetime] = None
    token_uri: str = "https://oauth2.googleapis.com/token"
    scopes: str = ""
    updated_at: datetime = Field(default_factory=datetime.utcnow)
