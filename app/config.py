"""Application configuration settings."""

from pathlib import Path
from typing import Set


class Settings:
    """Project configuration settings."""

    # Project Information
    PROJECT_NAME: str = "Geospatial File Measurement API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"

    # Uploads and Storage
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB

    # Allowed Geospatial Extensions
    ALLOWED_EXTENSIONS: Set[str] = {".zip", ".kml"}

    # Default fallback CRS if missing
    DEFAULT_CRS: str = "EPSG:4326"


settings = Settings()
# Ensure upload directory exists
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
