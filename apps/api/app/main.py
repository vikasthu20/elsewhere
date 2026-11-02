from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import api
from app.db import Base, engine
import app.models  # ensure models are registered with Base.metadata

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema changes are applied through Alembic before the API starts.
    yield

app = FastAPI(
    title="Elsewhere API",
    version="1.1.0",
    description="Travel discovery, itinerary planning and vehicle booking API",
    docs_url="/docs",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)
app.include_router(api, prefix="/api/v1")

@app.get("/health", tags=["operations"])
def health():
    return {"status": "ok", "service": "elsewhere-api", "version": app.version}
