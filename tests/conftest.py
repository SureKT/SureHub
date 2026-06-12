import os

# Dummy env vars MUST be set before importing anything from app/:
# Settings has required fields without defaults, app.database creates the
# engine at import time, and app.services.llm builds the Anthropic client at
# import time. DATABASE_URL points to in-memory SQLite so no test can ever
# touch the real surehub.db even through the module-level engine.
os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"
os.environ["TELEGRAM_BOT_TOKEN"] = "000000:test-telegram-token"
os.environ["TELEGRAM_ALLOWED_USER_IDS"] = "111"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["APP_ENV"] = "test"

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401  registers every table model in SQLModel.metadata

# Telegram user id matching TELEGRAM_ALLOWED_USER_IDS above
ALLOWED_USER_ID = 111


@pytest.fixture
def engine():
    # StaticPool: every Session shares the same in-memory DB connection,
    # so data committed by the code under test is visible to the test session.
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(engine):
    from fastapi.testclient import TestClient

    from app.database import get_session
    from app.main import app

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
