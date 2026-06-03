from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, workspaces, uploads, signals, backtests, jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="Backtesting LLM Selector",
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

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(workspaces.router, prefix="/api/workspaces", tags=["workspaces"])
app.include_router(uploads.router, prefix="/api/workspaces/{workspace_id}/uploads", tags=["uploads"])
app.include_router(signals.router, prefix="/api/workspaces/{workspace_id}/signals", tags=["signals"])
app.include_router(backtests.router, prefix="/api/workspaces/{workspace_id}/backtests", tags=["backtests"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
