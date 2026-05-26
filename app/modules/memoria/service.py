from sqlmodel import Session, select
from app.modules.memoria.models import Memory


def save_memory(session: Session, fact: str) -> Memory:
    memory = Memory(fact=fact)
    session.add(memory)
    session.commit()
    session.refresh(memory)
    return memory


def list_memories(session: Session) -> list[Memory]:
    return list(session.exec(select(Memory).order_by(Memory.date)).all())


def update_memory(session: Session, id: int, fact: str):
    memory = session.get(Memory, id)
    if not memory:
        return None
    memory.fact = fact
    session.add(memory)
    session.commit()
    session.refresh(memory)
    return memory


def delete_memory(session: Session, id: int) -> bool:
    memory = session.get(Memory, id)
    if not memory:
        return False
    session.delete(memory)
    session.commit()
    return True


def build_context(session: Session) -> str:
    memories = list_memories(session)
    if not memories:
        return ""
    facts = "\n".join(f"- {m.fact}" for m in memories)
    return f"Lo que sabes del usuario:\n{facts}"
