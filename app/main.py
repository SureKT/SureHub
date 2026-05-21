from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import create_db
from app.modules.spotify.router import router as spotify_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db()
    yield


app = FastAPI(title="SureHub", lifespan=lifespan)

app.include_router(spotify_router)


@app.get("/health")
def health():
    return {"status": "ok"}
