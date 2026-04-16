from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.config import settings
from app.core.logging import configure_logging
from app.db.session import engine

configure_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify DB connection, register pgvector extension check
    yield
    # Shutdown: close connection pool
    await engine.dispose()


app = FastAPI(
    title="Yearly Yields API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
