"""Coordinate Reference System (CRS) management and projection services."""

import logging
import math
from typing import Optional, Tuple, Union
import pyproj
from pyproj import CRS, Transformer
import shapely.ops
from shapely.geometry.base import BaseGeometry

logger = logging.getLogger(__name__)


class CRSService:
    """Service to identify, validate, and transform geometries between Coordinate Reference Systems.

    Strategy for Selecting Projected CRS:
    When geographic coordinates (such as EPSG:4326 with latitude/longitude in degrees)
    are provided, direct Euclidean calculations would yield meaningless degree-squared or
    degree measurements.

    This service implements a dynamic Centroid-Based Universal Transverse Mercator (UTM)
    projection strategy:
    1. Calculate the feature's geographic centroid (longitude, latitude).
    2. Determine the UTM zone: zone = floor((lon + 180) / 6) + 1.
    3. Choose WGS 84 / UTM North (EPSG:32601-32660) if latitude >= 0,
       or WGS 84 / UTM South (EPSG:32701-32760) if latitude < 0.
    4. For polar latitudes (> 84°N or < -80°S), fallback to Universal Polar Stereographic (UPS)
       or World Equal Area (EPSG:6933).

    This provides conformal, high-precision metric measurements (distortion < 0.1%)
    ideal for regional surveying and drone photogrammetry.
    """

    DEFAULT_GEOGRAPHIC_CRS = "EPSG:4326"

    @classmethod
    def parse_crs(cls, crs_input: Optional[Union[str, CRS]]) -> CRS:
        """Parse CRS from string, EPSG code, WKT, or CRS instance.

        Defaults to EPSG:4326 if not provided or unparseable.
        """
        if isinstance(crs_input, CRS):
            return crs_input

        if not crs_input or str(crs_input).strip() == "":
            return CRS.from_user_input(cls.DEFAULT_GEOGRAPHIC_CRS)

        cleaned = str(crs_input).strip()
        try:
            return CRS.from_user_input(cleaned)
        except Exception as e:
            logger.warning("Could not parse CRS '%s': %s. Falling back to %s", cleaned, e, cls.DEFAULT_GEOGRAPHIC_CRS)
            return CRS.from_user_input(cls.DEFAULT_GEOGRAPHIC_CRS)

    @classmethod
    def get_crs_representation(cls, crs_obj: CRS) -> str:
        """Returns a standardized string representation (e.g. 'EPSG:4326')."""
        try:
            epsg = crs_obj.to_epsg()
            if epsg:
                return f"EPSG:{epsg}"
            # Try authority name and code
            auth = crs_obj.to_authority()
            if auth:
                return f"{auth[0]}:{auth[1]}"
            return crs_obj.name or cls.DEFAULT_GEOGRAPHIC_CRS
        except Exception:
            return cls.DEFAULT_GEOGRAPHIC_CRS

    @classmethod
    def determine_projected_crs(cls, geom: BaseGeometry, source_crs: CRS) -> Tuple[CRS, str]:
        """Determine an appropriate projected CRS for metric measurements.

        If the source CRS is already projected with linear meter units, retains it.
        If geographic (degrees), computes the optimal UTM zone based on feature centroid.
        """
        # If already projected, check units
        if source_crs.is_projected:
            try:
                axis_units = [axis.unit_name.lower() for axis in source_crs.axis_info]
                if any("metre" in u or "meter" in u for u in axis_units):
                    rep = cls.get_crs_representation(source_crs)
                    return source_crs, rep
            except Exception:
                pass

        # Source is geographic (degrees) -> calculate centroid in WGS84
        try:
            if not source_crs.equals(CRS.from_user_input(cls.DEFAULT_GEOGRAPHIC_CRS)):
                # Reproject centroid to WGS84 first to get lon/lat
                to_wgs84 = Transformer.from_crs(source_crs, cls.DEFAULT_GEOGRAPHIC_CRS, always_xy=True)
                wgs84_geom = shapely.ops.transform(to_wgs84.transform, geom)
                centroid = wgs84_geom.centroid
            else:
                centroid = geom.centroid

            lon, lat = centroid.x, centroid.y

            # Clamp longitude to valid range [-180, 180]
            if lon >= 180.0:
                lon = 179.9999
            elif lon < -180.0:
                lon = -180.0

            # Polar handling
            if lat > 84.0:
                ups_north = "EPSG:32661"
                return CRS.from_user_input(ups_north), ups_north
            elif lat < -80.0:
                ups_south = "EPSG:32761"
                return CRS.from_user_input(ups_south), ups_south

            # UTM zone calculation: 1 to 60
            utm_zone = int(math.floor((lon + 180.0) / 6.0)) + 1
            utm_zone = max(1, min(60, utm_zone))

            if lat >= 0:
                epsg_code = 32600 + utm_zone
            else:
                epsg_code = 32700 + utm_zone

            target_str = f"EPSG:{epsg_code}"
            return CRS.from_user_input(target_str), target_str

        except Exception as e:
            logger.warning("Error determining UTM projection: %s. Using World Cylindrical Equal Area (EPSG:6933)", e)
            fallback = "EPSG:6933"
            return CRS.from_user_input(fallback), fallback

    @classmethod
    def transform_geometry(
        cls,
        geom: BaseGeometry,
        source_crs: Union[str, CRS],
        target_crs: Union[str, CRS],
    ) -> BaseGeometry:
        """Transform a Shapely geometry from source CRS to target CRS.

        Guarantees (x=lon, y=lat) coordinate order via always_xy=True.
        """
        src = cls.parse_crs(source_crs)
        dst = cls.parse_crs(target_crs)

        if src.equals(dst):
            return geom

        transformer = Transformer.from_crs(src, dst, always_xy=True)
        return shapely.ops.transform(transformer.transform, geom)
