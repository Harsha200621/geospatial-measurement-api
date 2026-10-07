"""Pytest fixtures and configuration."""

import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.storage import FileStorageRepository, storage_repo

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


@pytest.fixture(scope="session")
def client() -> TestClient:
    """FastAPI TestClient fixture."""
    return TestClient(app)


@pytest.fixture(scope="session")
def sample_kml_path() -> Path:
    """Path to sample KML file."""
    kml_path = SAMPLES_DIR / "sample_survey.kml"
    assert kml_path.exists(), f"Sample KML not found at {kml_path}"
    return kml_path


@pytest.fixture(scope="session")
def sample_shapefile_path() -> Path:
    """Path to sample Shapefile zip."""
    shp_path = SAMPLES_DIR / "sample_shapefile.zip"
    assert shp_path.exists(), f"Sample Shapefile zip not found at {shp_path}"
    return shp_path


@pytest.fixture
def isolated_storage(tmp_path: Path):
    """Fixture providing a fresh, isolated FileStorageRepository for testing."""
    repo = FileStorageRepository(storage_dir=tmp_path)
    return repo
