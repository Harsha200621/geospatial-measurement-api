"""Parser for ESRI Shapefile archives (.zip)."""

import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pyproj
import shapefile
from shapely.geometry import shape as to_shapely_shape
from shapely.validation import make_valid

from app.services.crs_service import CRSService
from app.services.parsers.base import BaseGeospatialParser, ParsedDataset, ParsedFeature

logger = logging.getLogger(__name__)


class ShapefileParser(BaseGeospatialParser):
    """Parser to unpack and read Shapefiles from zipped archives.

    Extracts:
    - Features and Shapely geometries
    - Associated DBF record attributes
    - CRS from .prj definition if available (or defaults to EPSG:4326)
    """

    def parse(self, file_path: Path) -> ParsedDataset:
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not zipfile.is_zipfile(file_path):
            raise ValueError("The provided file is not a valid ZIP archive.")

        # Extract safely into a temporary directory
        with tempfile.TemporaryDirectory(prefix="shp_extract_") as extract_dir:
            extract_path = Path(extract_dir)
            self._safe_extract_zip(file_path, extract_path)

            # Locate .shp files
            shp_files = list(extract_path.rglob("*.shp"))
            if not shp_files:
                raise ValueError("No .shp file found within the provided ZIP archive.")

            primary_shp = shp_files[0]
            logger.info("Found primary shapefile: %s", primary_shp.name)

            # Detect CRS from .prj file
            detected_crs = self._read_prj_crs(primary_shp)

            # Read features using PyShp
            features = self._read_shapefile_features(primary_shp, detected_crs)

            return ParsedDataset(
                features=features,
                crs=detected_crs,
                file_type="Shapefile",
                feature_count=len(features),
                metadata={
                    "shapefile_name": primary_shp.name,
                    "all_shp_files": [f.name for f in shp_files],
                },
            )

    def _safe_extract_zip(self, zip_path: Path, target_dir: Path) -> None:
        """Extract zip archive protecting against Zip Slip path traversal."""
        target_dir_resolved = target_dir.resolve()
        with zipfile.ZipFile(zip_path, "r") as archive:
            for member in archive.infolist():
                destination = (target_dir / member.filename).resolve()
                if not str(destination).startswith(str(target_dir_resolved)):
                    raise ValueError(f"Security error: Unsafe path in zip archive: {member.filename}")
            archive.extractall(target_dir)

    def _read_prj_crs(self, shp_path: Path) -> str:
        """Read and parse CRS from accompanying .prj file if present."""
        prj_path = shp_path.with_suffix(".prj")
        if not prj_path.exists():
            logger.warning("No .prj file found for %s. Defaulting to %s", shp_path.name, CRSService.DEFAULT_GEOGRAPHIC_CRS)
            return CRSService.DEFAULT_GEOGRAPHIC_CRS

        try:
            with open(prj_path, "r", encoding="utf-8", errors="ignore") as f:
                prj_wkt = f.read().strip()

            if not prj_wkt:
                return CRSService.DEFAULT_GEOGRAPHIC_CRS

            crs_obj = CRSService.parse_crs(prj_wkt)
            return CRSService.get_crs_representation(crs_obj)
        except Exception as e:
            logger.warning("Error reading .prj file %s: %s. Fallback to %s", prj_path, e, CRSService.DEFAULT_GEOGRAPHIC_CRS)
            return CRSService.DEFAULT_GEOGRAPHIC_CRS

    def _read_shapefile_features(self, shp_path: Path, crs_str: str) -> List[ParsedFeature]:
        """Read features, geometries, and attribute records from shapefile."""
        features: List[ParsedFeature] = []

        # Try utf-8 first, fallback to latin1 / cp1252 if necessary
        reader = None
        for enc in ["utf-8", "latin1", "cp1252"]:
            try:
                reader = shapefile.Reader(str(shp_path), encoding=enc)
                # Attempt reading first record to verify encoding
                if len(reader) > 0:
                    _ = reader.shapeRecord(0)
                break
            except Exception:
                reader = None

        if reader is None:
            # Fallback without explicit encoding
            reader = shapefile.Reader(str(shp_path))

        with reader:
            for idx, shape_rec in enumerate(reader.shapeRecords()):
                feature_id = str(idx + 1)
                try:
                    geo_interface = shape_rec.shape.__geo_interface__
                    if not geo_interface or not geo_interface.get("coordinates"):
                        # Empty geometry
                        continue

                    geom = to_shapely_shape(geo_interface)

                    if not geom.is_valid:
                        # Attempt to repair geometry
                        repaired = make_valid(geom)
                        if repaired and not repaired.is_empty:
                            geom = repaired

                    # Extract record properties safely
                    properties: Dict[str, Any] = {}
                    try:
                        record_dict = shape_rec.record.as_dict()
                        for k, v in record_dict.items():
                            # Ensure JSON serializable values
                            if hasattr(v, "isoformat"):
                                properties[k] = v.isoformat()
                            elif isinstance(v, bytes):
                                properties[k] = v.decode("utf-8", errors="replace")
                            else:
                                properties[k] = v
                    except Exception as prop_err:
                        logger.warning("Could not parse properties for feature %s: %s", feature_id, prop_err)

                    features.append(
                        ParsedFeature(
                            feature_id=feature_id,
                            geometry_type=geom.geom_type,
                            geometry=geom,
                            crs=crs_str,
                            properties=properties,
                            is_valid=geom.is_valid,
                        )
                    )
                except Exception as feat_err:
                    logger.warning("Skipping corrupted shape record %s: %s", feature_id, feat_err)

        return features
