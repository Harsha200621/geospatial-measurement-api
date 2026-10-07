"""Base classes and data structures for geospatial file parsers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from shapely.geometry.base import BaseGeometry


@dataclass
class ParsedFeature:
    """Standardized representation of an extracted geospatial feature."""
    feature_id: str
    geometry_type: str
    geometry: BaseGeometry
    crs: str
    properties: Dict[str, Any] = field(default_factory=dict)
    is_valid: bool = True
    error_message: Optional[str] = None


@dataclass
class ParsedDataset:
    """Container for the output of parsing a geospatial file."""
    features: List[ParsedFeature]
    crs: str
    file_type: str
    feature_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseGeospatialParser(ABC):
    """Abstract base class that all geospatial format parsers must implement."""

    @abstractmethod
    def parse(self, file_path: Path) -> ParsedDataset:
        """Parse geospatial file from disk and return structured features and metadata.

        Args:
            file_path: Absolute path to the file.

        Returns:
            ParsedDataset containing parsed features, CRS, and metadata.

        Raises:
            ValueError: If the file format or contents are invalid.
            FileNotFoundError: If the file does not exist.
        """
        pass
