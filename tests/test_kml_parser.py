"""Unit tests for KML parser."""

import tempfile
from pathlib import Path
import pytest

from app.services.parsers.kml_parser import KMLParser


def test_parse_valid_kml(sample_kml_path: Path):
    """Test parsing a valid KML file with Polygon, LineString, and Point."""
    parser = KMLParser()
    dataset = parser.parse(sample_kml_path)

    assert dataset.file_type == "KML"
    assert dataset.crs == "EPSG:4326"
    assert dataset.feature_count == 3
    assert len(dataset.features) == 3

    geom_types = [f.geometry_type for f in dataset.features]
    assert "Polygon" in geom_types
    assert "LineString" in geom_types
    assert "Point" in geom_types

    # Check properties extracted from Placemark 1
    poly_feature = next(f for f in dataset.features if f.geometry_type == "Polygon")
    assert poly_feature.properties.get("name") == "Agricultural Field 1"
    assert poly_feature.properties.get("crop_type") == "Paddy"
    assert poly_feature.is_valid is True


def test_parse_malformed_xml():
    """Test that malformed XML raises ValueError gracefully."""
    with tempfile.NamedTemporaryFile(suffix=".kml", delete=False, mode="w", encoding="utf-8") as f:
        f.write("<kml><Document><unclosed_tag></kml>")
        temp_path = Path(f.name)

    try:
        parser = KMLParser()
        with pytest.raises(ValueError, match="Invalid KML XML"):
            parser.parse(temp_path)
    finally:
        temp_path.unlink()


def test_parse_nonexistent_file():
    """Test that non-existent file raises FileNotFoundError."""
    parser = KMLParser()
    with pytest.raises(FileNotFoundError):
        parser.parse(Path("non_existent_file.kml"))
