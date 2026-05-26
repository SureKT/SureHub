from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import create_db
from app.routers.finanzas import router as finance_router
from app.routers.memoria import router as memory_router
from app.routers.recurrentes import router as recurring_router
from app.modules.spotify.router import router as spotify_router
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db()
    yield


app = FastAPI(title="SureHub", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(finance_router)
app.include_router(memory_router)
app.include_router(recurring_router)
app.include_router(spotify_router)


@app.get("/health")
def health():
    return {"status": "ok"}
