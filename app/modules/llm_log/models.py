from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


class LLMCall(SQLModel, table=True):
    __tablename__ = "llm_calls"

    id: int | None = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime)
    function: str
    tier: str
    model_requested: str
    model_served: str = ""
    fell_back: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    prompt: str = ""
    output: str = ""
    success: bool = True
    error: str | None = None
