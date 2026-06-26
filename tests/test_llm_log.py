from sqlmodel import select

from app.modules.llm_log.models import LLMCall
from app.modules.llm_log.service import log_call


def test_log_call_persists_row(session):
    call = log_call(
        session,
        function="complete_tags",
        tier="local_ok",
        model_requested="anthropic/haiku",
        model_served="anthropic/haiku",
        fell_back=False,
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.0001,
        latency_ms=120,
        prompt="some prompt",
        output="some output",
        success=True,
        error=None,
    )
    assert call.id is not None
    rows = session.exec(select(LLMCall)).all()
    assert len(rows) == 1
    assert rows[0].function == "complete_tags"
    assert rows[0].fell_back is False
    assert rows[0].cost_usd == 0.0001
