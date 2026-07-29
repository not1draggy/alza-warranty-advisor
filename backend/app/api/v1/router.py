"""API v1 router."""

from fastapi import APIRouter

from app.api.v1 import analysis, auth, health, products

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(analysis.router)
api_router.include_router(products.router)
