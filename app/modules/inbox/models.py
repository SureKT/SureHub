from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class InboxItem(SQLModel, table=True):
    __tablename__ = "inbox_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str = Field(index=True, unique=True)  # nombre del .md en inbox/
    excerpt: str = ""                                # primeros ~200 chars
    source: str = ""                                 # telegram | telegram-voice | ...
    category: str = "uncertain"                      # task | note | uncertain
    proposed_text: str = ""
    status: str = "pending"                          # pending | approved | archived | discarded
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
