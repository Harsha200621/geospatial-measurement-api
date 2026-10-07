"""Unit tests for CRS handling and dynamic UTM reprojection."""

import pytest
from pyproj import CRS
from shapely.geometry import LineString, Point, Polygon

from app.services.crs_service import CRSService


def test_parse_crs_standard_and_epsg():
    """Test parsing standard EPSG codes and fallbacks."""
    crs_4326 = CRSService.parse_crs("EPSG:4326")
    assert crs_4326.to_epsg() == 4326

    crs_3857 = CRSService.parse_crs("EPSG:3857")
    assert crs_3857.to_epsg() == 3857

    # Blank / None should fallback to default EPSG:4326
    fallback_crs = CRSService.parse_crs("")
    assert fallback_crs.to_epsg() == 4326


def test_utm_zone_determination_bangalore():
    """Test UTM zone determination for Bangalore, India (lon 77.58, lat 12.96).

    Bangalore is located in UTM Zone 43 North (EPSG:32643).
    """
    poly = Polygon([(77.58, 12.96), (77.60, 12.96), (77.60, 12.98), (77.58, 12.98), (77.58, 12.96)])
    source_crs = CRSService.parse_crs("EPSG:4326")

    target_crs, code = CRSService.determine_projected_crs(poly, source_crs)
    assert code == "EPSG:32643"
    assert target_crs.to_epsg() == 32643


def test_utm_zone_determination_southern_hemisphere():
    """Test UTM zone determination for Sydney, Australia (lon 151.2, lat -33.8).

    Sydney is located in UTM Zone 56 South (EPSG:32756).
    """
    poly = Polygon([(151.20, -33.85), (151.22, -33.85), (151.22, -33.87), (151.20, -33.87), (151.20, -33.85)])
    source_crs = CRSService.parse_crs("EPSG:4326")

    target_crs, code = CRSService.determine_projected_crs(poly, source_crs)
    assert code == "EPSG:32756"
    assert target_crs.to_epsg() == 32756


def test_projected_crs_preservation():
    """If geometry is already in a metric projected CRS (e.g. EPSG:3857), it should be preserved."""
    poly = Polygon([(1000, 1000), (2000, 1000), (2000, 2000), (1000, 2000), (1000, 1000)])
    proj_crs = CRSService.parse_crs("EPSG:3857")

    target_crs, code = CRSService.determine_projected_crs(poly, proj_crs)
    assert "3857" in code


def test_transform_geometry_reprojection():
    """Test transforming a geographic polygon into a metric projected geometry."""
    # A ~100m x 100m square in degrees near the equator (~0.001 deg)
    poly = Polygon([(0.0, 0.0), (0.001, 0.0), (0.001, 0.001), (0.0, 0.001), (0.0, 0.0)])
    source_crs = "EPSG:4326"
    target_crs = "EPSG:32631"  # UTM Zone 31N at prime meridian

    projected_geom = CRSService.transform_geometry(poly, source_crs, target_crs)
    assert projected_geom.is_valid
    # 0.001 degree ~ 111 meters. Area ~ 111m * 111m ~ 12300 sq meters.
    assert 10000.0 < projected_geom.area < 15000.0
