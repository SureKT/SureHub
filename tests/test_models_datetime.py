from datetime import datetime

import pytest
from sqlalchemy import DateTime
from sqlmodel import SQLModel

from app.modules.calendar.models import GoogleToken

DATETIME_COLUMNS = [
    col
    for table in SQLModel.metadata.sorted_tables
    for col in table.columns
    if isinstance(col.type, DateTime) or "DateTime" in type(col.type).__name__
]


def test_there_are_datetime_columns():
    assert len(DATETIME_COLUMNS) >= 8


# sqlmodel>=0.0.45 mapea `datetime` a UTCDateTime: rechaza valores naive al escribir,
# devuelve aware al leer y procesa como datetime los bounds string de finanzas.
# Las columnas deben seguir siendo DateTime naive (lo que sqlmodel generaba antes).
@pytest.mark.parametrize("col", DATETIME_COLUMNS, ids=lambda c: f"{c.table.name}.{c.name}")
def test_datetime_columns_are_plain_naive_datetime(col):
    assert type(col.type) is DateTime
    assert col.type.timezone is False


def test_google_token_expiry_roundtrips_naive(session):
    # google-auth compara expiry con un utcnow naive: un valor aware rompería el refresh
    expiry = datetime(2026, 10, 18, 12, 0, 0)
    session.add(GoogleToken(access_token="a", refresh_token="r", token_expiry=expiry))
    session.commit()
    session.expire_all()

    token = session.get(GoogleToken, 1)
    assert token.token_expiry == expiry
    assert token.token_expiry.tzinfo is None
    assert token.updated_at.tzinfo is None
