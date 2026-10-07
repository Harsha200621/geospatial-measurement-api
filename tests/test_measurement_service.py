"""Unit tests for MeasurementService metric calculations."""

from shapely.geometry import GeometryCollection, LineString, Point, Polygon

from app.services.measurement_service import MeasurementService
from app.services.parsers.base import ParsedDataset, ParsedFeature


def test_polygon_area_calculation():
    """Verify polygon area is properly calculated in sq meters and hectares."""
    # Create ~500m x 500m polygon in Bangalore
    poly = Polygon([(77.580, 12.960), (77.585, 12.960), (77.585, 12.965), (77.580, 12.965), (77.580, 12.960)])
    feature = ParsedFeature(
        feature_id="poly_1",
        geometry_type="Polygon",
        geometry=poly,
        crs="EPSG:4326",
        properties={"name": "Test Field"},
    )
    dataset = ParsedDataset(
        features=[feature],
        crs="EPSG:4326",
        file_type="KML",
        feature_count=1,
    )

    res = MeasurementService.process_dataset("file_1", "test.kml", dataset)
    assert res.feature_count == 1
    assert res.summary.polygon_count == 1

    feature_out = res.features[0]
    assert feature_out.status == "PROCESSED"
    assert feature_out.measurements is not None
    assert feature_out.measurements.area_sq_meters > 250000.0  # ~300k m²
    assert feature_out.measurements.area_hectares > 25.0
    assert feature_out.measurements.length_meters > 1800.0  # Perimeter


def test_linestring_length_calculation():
    """Verify linestring length is calculated in meters and kilometers."""
    line = LineString([(77.580, 12.960), (77.585, 12.965)])
    feature = ParsedFeature(
        feature_id="line_1",
        geometry_type="LineString",
        geometry=line,
        crs="EPSG:4326",
        properties={"route": "Path A"},
    )
    dataset = ParsedDataset(
        features=[feature],
        crs="EPSG:4326",
        file_type="KML",
        feature_count=1,
    )

    res = MeasurementService.process_dataset("file_2", "line.kml", dataset)
    assert res.summary.linestring_count == 1

    feature_out = res.features[0]
    assert feature_out.status == "PROCESSED"
    assert feature_out.measurements.length_meters > 700.0
    assert feature_out.measurements.length_km > 0.7


def test_point_graceful_handling():
    """Verify points do not crash and report NOT_MEASURED status."""
    pt = Point(77.582, 12.962)
    feature = ParsedFeature(
        feature_id="pt_1",
        geometry_type="Point",
        geometry=pt,
        crs="EPSG:4326",
        properties={"type": "GCP"},
    )
    dataset = ParsedDataset(
        features=[feature],
        crs="EPSG:4326",
        file_type="KML",
        feature_count=1,
    )

    res = MeasurementService.process_dataset("file_3", "point.kml", dataset)
    assert res.summary.point_count == 1

    feature_out = res.features[0]
    assert feature_out.status == "NOT_MEASURED"
    assert feature_out.measurements.area_sq_meters is None
    assert feature_out.measurements.length_meters is None
    assert "No measurement required" in feature_out.measurements.note


def test_unsupported_geometry_graceful_handling():
    """Verify unsupported geometry types do not crash and report UNSUPPORTED status."""
    gc = GeometryCollection()
    feature = ParsedFeature(
        feature_id="gc_1",
        geometry_type="GeometryCollection",
        geometry=gc,
        crs="EPSG:4326",
        properties={},
    )
    dataset = ParsedDataset(
        features=[feature],
        crs="EPSG:4326",
        file_type="KML",
        feature_count=1,
    )

    res = MeasurementService.process_dataset("file_4", "gc.kml", dataset)
    assert res.summary.unsupported_count == 1

    feature_out = res.features[0]
    assert feature_out.status == "UNSUPPORTED"
    assert "not supported" in feature_out.measurements.note
