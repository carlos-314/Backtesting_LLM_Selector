"""Router raíz de /api/v1."""
from fastapi import APIRouter

from app.infrastructure.web.v1 import admin_users, auth, backtests, health, screening

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(health.router)
api_v1.include_router(auth.router)
api_v1.include_router(admin_users.router)
api_v1.include_router(screening.router)
api_v1.include_router(backtests.router)
