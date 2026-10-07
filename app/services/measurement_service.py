"""Service to process geospatial features, project coordinates, and calculate measurements."""

import logging
from typing import Any, Dict, List, Tuple
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

from app.schemas.measurement import (
    FeatureMeasurement,
    FileMeasurementsResponse,
    MeasurementSummary,
    MeasurementValue,
)
from app.services.crs_service import CRSService
from app.services.parsers.base import ParsedDataset, ParsedFeature

logger = logging.getLogger(__name__)


class MeasurementService:
    """Calculates geometric measurements for geospatial features.

    Converts geographic coordinates (e.g., EPSG:4326) to appropriate local
    projected coordinate systems (e.g., UTM) prior to metric calculations.
    """

    POLYGON_TYPES = {"Polygon", "MultiPolygon"}
    LINESTRING_TYPES = {"LineString", "MultiLineString"}
    POINT_TYPES = {"Point", "MultiPoint"}

    @classmethod
    def process_dataset(cls, file_id: str, filename: str, dataset: ParsedDataset) -> FileMeasurementsResponse:
        """Process all features in a dataset and calculate measurements.

        Args:
            file_id: Unique file identifier.
            filename: Original uploaded filename.
            dataset: Parsed dataset containing features and CRS.

        Returns:
            FileMeasurementsResponse containing measurements, GeoJSON geometries, and summary.
        """
        source_crs_obj = CRSService.parse_crs(dataset.crs)
        source_crs_str = CRSService.get_crs_representation(source_crs_obj)

        processed_features: List[FeatureMeasurement] = []
        total_area_sq_m = 0.0
        total_length_m = 0.0
        polygon_cnt = 0
        linestring_cnt = 0
        point_cnt = 0
        unsupported_cnt = 0

        for feature in dataset.features:
            geom = feature.geometry
            geom_type = feature.geometry_type

            # Transform geometry to projected CRS for accurate metric calculations
            try:
                target_crs_obj, projected_crs_str = CRSService.determine_projected_crs(geom, source_crs_obj)
                projected_geom = CRSService.transform_geometry(geom, source_crs_obj, target_crs_obj)
            except Exception as proj_err:
                logger.error("Failed to reproject feature %s: %s", feature.feature_id, proj_err)
                projected_geom = None
                projected_crs_str = None

            # Calculate measurements based on geometry type
            measurement_val, status = cls._calculate_feature_measurement(geom_type, projected_geom)

            # Update aggregation counters
            if geom_type in cls.POLYGON_TYPES:
                polygon_cnt += 1
                if measurement_val and measurement_val.area_sq_meters is not None:
                    total_area_sq_m += measurement_val.area_sq_meters
            elif geom_type in cls.LINESTRING_TYPES:
                linestring_cnt += 1
                if measurement_val and measurement_val.length_meters is not None:
                    total_length_m += measurement_val.length_meters
            elif geom_type in cls.POINT_TYPES:
                point_cnt += 1
            else:
                unsupported_cnt += 1

            # Convert Shapely geometry to standard GeoJSON dictionary
            try:
                geojson_geom = mapping(geom)
            except Exception:
                geojson_geom = {"type": geom_type, "coordinates": []}

            feature_res = FeatureMeasurement(
                feature_id=feature.feature_id,
                geometry_type=geom_type,
                geometry=geojson_geom,
                crs=source_crs_str,
                projected_crs=projected_crs_str,
                properties=feature.properties,
                measurements=measurement_val,
                status=status,
            )
            processed_features.append(feature_res)

        summary = MeasurementSummary(
            total_area_sq_meters=round(total_area_sq_m, 4),
            total_area_hectares=round(total_area_sq_m / 10000.0, 6),
            total_length_meters=round(total_length_m, 4),
            total_length_km=round(total_length_m / 1000.0, 6),
            polygon_count=polygon_cnt,
            linestring_count=linestring_cnt,
            point_count=point_cnt,
            unsupported_count=unsupported_cnt,
        )

        return FileMeasurementsResponse(
            id=file_id,
            filename=filename,
            feature_count=len(processed_features),
            crs=source_crs_str,
            summary=summary,
            features=processed_features,
        )

    @classmethod
    def _calculate_feature_measurement(
        cls, geom_type: str, projected_geom: BaseGeometry
    ) -> Tuple[MeasurementValue, str]:
        """Calculate measurements for an individual geometry safely."""
        if projected_geom is None or projected_geom.is_empty:
            return (
                MeasurementValue(note="Geometry is empty or could not be projected."),
                "ERROR",
            )

        if geom_type in cls.POLYGON_TYPES:
            try:
                area_m2 = round(float(projected_geom.area), 4)
                area_ha = round(area_m2 / 10000.0, 6)
                area_km2 = round(area_m2 / 1000000.0, 6)
                perimeter_m = round(float(projected_geom.length), 4)
                return (
                    MeasurementValue(
                        area_sq_meters=area_m2,
                        area_hectares=area_ha,
                        area_sq_km=area_km2,
                        length_meters=perimeter_m,
                        note="Area and perimeter calculated via metric projection.",
                    ),
                    "PROCESSED",
                )
            except Exception as e:
                logger.error("Error calculating polygon area: %s", e)
                return (MeasurementValue(note=f"Area calculation failed: {e}"), "ERROR")

        elif geom_type in cls.LINESTRING_TYPES:
            try:
                length_m = round(float(projected_geom.length), 4)
                length_km = round(length_m / 1000.0, 6)
                return (
                    MeasurementValue(
                        length_meters=length_m,
                        length_km=length_km,
                        note="Length calculated via metric projection.",
                    ),
                    "PROCESSED",
                )
            except Exception as e:
                logger.error("Error calculating line length: %s", e)
                return (MeasurementValue(note=f"Length calculation failed: {e}"), "ERROR")

        elif geom_type in cls.POINT_TYPES:
            return (
                MeasurementValue(note="No measurement required for Point geometry."),
                "NOT_MEASURED",
            )

        else:
            # Handle unsupported geometry types gracefully without crashing
            logger.info("Unsupported geometry type encountered: %s", geom_type)
            return (
                MeasurementValue(
                    note=f"Geometry type '{geom_type}' is not supported for measurement calculation."
                ),
                "UNSUPPORTED",
            )
