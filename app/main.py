from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import create_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db()
    yield


app = FastAPI(title="SureHub", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}
