"""Pydantic schemas for geospatial measurements and feature outputs."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MeasurementValue(BaseModel):
    """Calculated measurement metrics for a feature."""
    area_sq_meters: Optional[float] = Field(None, description="Calculated area in square meters (m²)")
    area_hectares: Optional[float] = Field(None, description="Calculated area in hectares (ha)")
    area_sq_km: Optional[float] = Field(None, description="Calculated area in square kilometers (km²)")
    length_meters: Optional[float] = Field(None, description="Calculated length or perimeter in meters (m)")
    length_km: Optional[float] = Field(None, description="Calculated length in kilometers (km)")
    note: Optional[str] = Field(None, description="Descriptive status note (e.g. why no measurement)")


class FeatureMeasurement(BaseModel):
    """Measurement and metadata for an individual geospatial feature."""
    feature_id: str = Field(..., description="Unique identifier or index of the feature")
    geometry_type: str = Field(..., description="OGC geometry type (Polygon, LineString, Point, etc.)")
    geometry: Dict[str, Any] = Field(..., description="GeoJSON representation of the feature geometry")
    crs: str = Field(..., description="Original Coordinate Reference System of the file")
    projected_crs: Optional[str] = Field(
        None, description="Projected CRS used for high-precision metric calculations (e.g. EPSG:32643)"
    )
    properties: Dict[str, Any] = Field(default_factory=dict, description="Feature attributes and properties")
    measurements: Optional[MeasurementValue] = Field(
        None, description="Measurement metrics (area, length) or null if not applicable"
    )
    status: str = Field("PROCESSED", description="Processing state: PROCESSED, NOT_MEASURED, UNSUPPORTED")


class MeasurementSummary(BaseModel):
    """Aggregated summary across all features within the file."""
    total_area_sq_meters: float = Field(0.0, description="Sum of all polygon areas in square meters")
    total_area_hectares: float = Field(0.0, description="Sum of all polygon areas in hectares")
    total_length_meters: float = Field(0.0, description="Sum of all linestring lengths in meters")
    total_length_km: float = Field(0.0, description="Sum of all linestring lengths in kilometers")
    polygon_count: int = Field(0, description="Count of Polygon and MultiPolygon features")
    linestring_count: int = Field(0, description="Count of LineString and MultiLineString features")
    point_count: int = Field(0, description="Count of Point and MultiPoint features")
    unsupported_count: int = Field(0, description="Count of unsupported or invalid geometries")


class FileMeasurementsResponse(BaseModel):
    """Response returned by GET /api/files/{id}/measurements/ endpoint."""
    id: str = Field(..., description="ID of the geospatial file")
    filename: str = Field(..., description="Original filename")
    feature_count: int = Field(0, description="Total number of features processed")
    crs: str = Field(..., description="Original CRS of the uploaded file")
    summary: MeasurementSummary = Field(..., description="Aggregated measurement summary")
    features: List[FeatureMeasurement] = Field(
        default_factory=list, description="List of processed features and their measurements"
    )
