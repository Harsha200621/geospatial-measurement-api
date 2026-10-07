"""API v1 router aggregator."""

from fastapi import APIRouter
from app.api.v1.endpoints import router as files_router

api_router = APIRouter()
api_router.include_router(files_router)
