from sqlmodel import select

from app.modules.inbox.models import InboxItem


def test_inbox_item_persists(session):
    item = InboxItem(filename="2026-06-18-1000-x.md", category="task", proposed_text="comprar pan")
    session.add(item)
    session.commit()

    rows = session.exec(select(InboxItem)).all()
    assert len(rows) == 1
    assert rows[0].status == "pending"
    assert rows[0].filename == "2026-06-18-1000-x.md"
