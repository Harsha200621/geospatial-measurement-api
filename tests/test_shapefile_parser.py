"""Unit tests for Shapefile ZIP archive parser."""

import tempfile
import zipfile
from pathlib import Path
import pytest

from app.services.parsers.shapefile_parser import ShapefileParser


def test_parse_valid_shapefile_zip(sample_shapefile_path: Path):
    """Test parsing a valid Shapefile zipped archive."""
    parser = ShapefileParser()
    dataset = parser.parse(sample_shapefile_path)

    assert dataset.file_type == "Shapefile"
    assert "EPSG:4326" in dataset.crs
    assert dataset.feature_count == 2
    assert len(dataset.features) == 2

    # Check geometries
    for feat in dataset.features:
        assert feat.geometry_type == "Polygon"
        assert feat.geometry.is_valid
        assert "PLOT_NAME" in feat.properties
        assert "ZONE" in feat.properties


def test_parse_zip_missing_shp():
    """Test that a ZIP without a .shp file raises ValueError."""
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        temp_zip_path = Path(f.name)

    try:
        # Create zip with dummy txt file
        with zipfile.ZipFile(temp_zip_path, "w") as zf:
            zf.writestr("notes.txt", "No shapefile here!")

        parser = ShapefileParser()
        with pytest.raises(ValueError, match="No .shp file found"):
            parser.parse(temp_zip_path)
    finally:
        temp_zip_path.unlink()


def test_parse_invalid_zip_format():
    """Test that a corrupted non-zip file raises ValueError."""
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        f.write(b"not a valid zip binary content")
        temp_file_path = Path(f.name)

    try:
        parser = ShapefileParser()
        with pytest.raises(ValueError, match="not a valid ZIP archive"):
            parser.parse(temp_file_path)
    finally:
        temp_file_path.unlink()
