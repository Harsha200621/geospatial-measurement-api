import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.config import settings

STATIC_DIR = Path(__file__).resolve().parent / "static"
SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"

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

# Mount samples directory for static download
if SAMPLES_DIR.exists():
    app.mount("/samples", StaticFiles(directory=str(SAMPLES_DIR)), name="samples")


@app.get(
    "/",
    tags=["Root"],
    summary="Root service information or interactive dashboard",
)
async def root(request: Request):
    """Serves the interactive map dashboard to browsers and API metadata to JSON clients."""
    accept = request.headers.get("accept", "")
    index_file = STATIC_DIR / "index.html"
    if "text/html" in accept and index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "documentation": "/docs",
        "dashboard": "/dashboard",
    }


@app.get(
    "/dashboard",
    tags=["Dashboard"],
    summary="Interactive Leaflet Map Dashboard",
)
async def dashboard():
    """Serves the interactive Leaflet map dashboard."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    return JSONResponse(status_code=404, content={"detail": "Dashboard template not found"})


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
