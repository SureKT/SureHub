from sqlmodel import Session

from app.modules.llm_log.models import LLMCall


def log_call(session: Session, **fields) -> LLMCall:
    call = LLMCall(**fields)
    session.add(call)
    session.commit()
    session.refresh(call)
    return call
