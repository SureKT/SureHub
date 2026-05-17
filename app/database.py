from sqlmodel import SQLModel, create_engine, Session
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "local",
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)


def create_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
