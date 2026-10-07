"""Parser for Keyhole Markup Language (KML) geospatial files."""

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)
from shapely.geometry.base import BaseGeometry
from shapely.validation import make_valid

from app.services.parsers.base import BaseGeospatialParser, ParsedDataset, ParsedFeature

logger = logging.getLogger(__name__)


class KMLParser(BaseGeospatialParser):
    """Parser to extract Placemark geometries and attributes from KML files.

    KML files canonically use the WGS 84 geographic coordinate reference system (EPSG:4326).
    Coordinates are formatted as lon,lat[,altitude].
    """

    DEFAULT_KML_CRS = "EPSG:4326"

    def parse(self, file_path: Path) -> ParsedDataset:
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except ET.ParseError as e:
            raise ValueError(f"Invalid KML XML syntax: {e}")
        except Exception as e:
            raise ValueError(f"Failed to read KML file: {e}")

        features = self._extract_placemarks(root)

        return ParsedDataset(
            features=features,
            crs=self.DEFAULT_KML_CRS,
            file_type="KML",
            feature_count=len(features),
            metadata={"source_file": file_path.name},
        )

    def _strip_ns(self, tag: str) -> str:
        """Strip XML namespace prefix from tag."""
        return tag.split("}")[-1] if "}" in tag else tag

    def _extract_placemarks(self, root: ET.Element) -> List[ParsedFeature]:
        """Traverse XML and extract features from each Placemark."""
        features: List[ParsedFeature] = []
        feature_counter = 0

        for elem in root.iter():
            if self._strip_ns(elem.tag).lower() == "placemark":
                feature_counter += 1
                feature_id = elem.attrib.get("id") or str(feature_counter)

                # Extract properties
                properties = self._extract_properties(elem)

                # Extract geometry
                geom = self._extract_geometry(elem)
                if geom is None or geom.is_empty:
                    logger.debug("Placemark %s has no geometry, skipping.", feature_id)
                    continue

                if not geom.is_valid:
                    repaired = make_valid(geom)
                    if repaired and not repaired.is_empty:
                        geom = repaired

                features.append(
                    ParsedFeature(
                        feature_id=feature_id,
                        geometry_type=geom.geom_type,
                        geometry=geom,
                        crs=self.DEFAULT_KML_CRS,
                        properties=properties,
                        is_valid=geom.is_valid,
                    )
                )

        return features

    def _extract_properties(self, placemark: ET.Element) -> Dict[str, Any]:
        """Extract name, description, and ExtendedData from Placemark."""
        props: Dict[str, Any] = {}

        for child in placemark:
            tag = self._strip_ns(child.tag).lower()
            if tag == "name" and child.text:
                props["name"] = child.text.strip()
            elif tag == "description" and child.text:
                props["description"] = child.text.strip()
            elif tag == "extendeddata":
                for ext in child.iter():
                    ext_tag = self._strip_ns(ext.tag).lower()
                    if ext_tag == "data":
                        name_attr = ext.attrib.get("name")
                        val_elem = ext.find("{*}value")
                        if val_elem is None:
                            # Search without namespace
                            for sub in ext:
                                if self._strip_ns(sub.tag).lower() == "value":
                                    val_elem = sub
                                    break
                        if name_attr and val_elem is not None and val_elem.text:
                            props[name_attr] = val_elem.text.strip()
                    elif ext_tag == "simpledata":
                        name_attr = ext.attrib.get("name")
                        if name_attr and ext.text:
                            props[name_attr] = ext.text.strip()

        return props

    def _extract_geometry(self, placemark: ET.Element) -> Optional[BaseGeometry]:
        """Identify and construct Shapely geometry from Placemark."""
        for child in placemark:
            tag = self._strip_ns(child.tag).lower()
            if tag == "polygon":
                return self._parse_polygon(child)
            elif tag == "linestring":
                return self._parse_linestring(child)
            elif tag == "point":
                return self._parse_point(child)
            elif tag == "multigeometry":
                return self._parse_multigeometry(child)

        return None

    def _parse_coords(self, coords_text: str) -> List[Tuple[float, float]]:
        """Parse KML coordinate string: 'lon,lat[,alt] lon,lat[,alt]'."""
        coords: List[Tuple[float, float]] = []
        if not coords_text:
            return coords

        for token in coords_text.strip().split():
            parts = token.split(",")
            if len(parts) >= 2:
                try:
                    lon = float(parts[0])
                    lat = float(parts[1])
                    coords.append((lon, lat))
                except ValueError:
                    continue
        return coords

    def _parse_polygon(self, poly_elem: ET.Element) -> Optional[Polygon]:
        """Parse KML <Polygon> into Shapely Polygon."""
        exterior_coords: List[Tuple[float, float]] = []
        interiors: List[List[Tuple[float, float]]] = []

        for elem in poly_elem.iter():
            tag = self._strip_ns(elem.tag).lower()
            if tag == "outerboundaryis":
                for coord_elem in elem.iter():
                    if self._strip_ns(coord_elem.tag).lower() == "coordinates" and coord_elem.text:
                        exterior_coords = self._parse_coords(coord_elem.text)
            elif tag == "innerboundaryis":
                for coord_elem in elem.iter():
                    if self._strip_ns(coord_elem.tag).lower() == "coordinates" and coord_elem.text:
                        hole = self._parse_coords(coord_elem.text)
                        if len(hole) >= 3:
                            interiors.append(hole)

        if len(exterior_coords) >= 3:
            try:
                return Polygon(shell=exterior_coords, holes=interiors)
            except Exception as e:
                logger.warning("Error creating Polygon: %s", e)
                return None
        return None

    def _parse_linestring(self, line_elem: ET.Element) -> Optional[LineString]:
        """Parse KML <LineString> into Shapely LineString."""
        for elem in line_elem.iter():
            if self._strip_ns(elem.tag).lower() == "coordinates" and elem.text:
                coords = self._parse_coords(elem.text)
                if len(coords) >= 2:
                    try:
                        return LineString(coords)
                    except Exception as e:
                        logger.warning("Error creating LineString: %s", e)
                        return None
        return None

    def _parse_point(self, pt_elem: ET.Element) -> Optional[Point]:
        """Parse KML <Point> into Shapely Point."""
        for elem in pt_elem.iter():
            if self._strip_ns(elem.tag).lower() == "coordinates" and elem.text:
                coords = self._parse_coords(elem.text)
                if coords:
                    return Point(coords[0])
        return None

    def _parse_multigeometry(self, multi_elem: ET.Element) -> Optional[BaseGeometry]:
        """Parse KML <MultiGeometry> into Shapely Multi/Collection geometry."""
        geoms: List[BaseGeometry] = []
        for child in multi_elem:
            tag = self._strip_ns(child.tag).lower()
            if tag == "polygon":
                poly = self._parse_polygon(child)
                if poly:
                    geoms.append(poly)
            elif tag == "linestring":
                line = self._parse_linestring(child)
                if line:
                    geoms.append(line)
            elif tag == "point":
                pt = self._parse_point(child)
                if pt:
                    geoms.append(pt)

        if not geoms:
            return None

        # Consolidate into specific Multi geometry if homogenous
        if all(isinstance(g, Polygon) for g in geoms):
            return MultiPolygon(geoms)
        elif all(isinstance(g, LineString) for g in geoms):
            return MultiLineString(geoms)
        elif all(isinstance(g, Point) for g in geoms):
            return MultiPoint(geoms)
        else:
            return GeometryCollection(geoms)
