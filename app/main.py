"""FastAPI application entrypoint for Geospatial File Measurement API."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.config import settings

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("geospatial_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    logger.info("Initializing %s v%s...", settings.PROJECT_NAME, settings.VERSION)
    yield
    logger.info("Shutting down %s...", settings.PROJECT_NAME)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Production-grade FastAPI service that accepts geospatial files (ESRI Shapefiles in .zip, or .kml), "
        "extracts geographic features, dynamically transforms coordinates to appropriate metric projected "
        "coordinate systems (e.g. local UTM), and computes geometric measurements (area, length, perimeter)."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for web clients / GIS dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get(
    "/",
    tags=["Root"],
    summary="Root service information",
)
async def root():
    """Service status and quick links to API documentation."""
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "documentation": "/docs",
        "endpoints": {
            "upload_file": "POST /api/files/",
            "get_file_info": "GET /api/files/{id}/",
            "get_measurements": "GET /api/files/{id}/measurements/",
            "list_files": "GET /api/files/",
        },
    }


@app.get(
    "/api/health",
    tags=["Health"],
    summary="Health check probe",
)
async def health_check():
    """Health check endpoint for liveness and readiness monitoring."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }
