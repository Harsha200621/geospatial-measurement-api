"""Pydantic schemas for file upload and file information responses."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class FileStatus(str, Enum):
    """Lifecycle status of an uploaded geospatial file."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FileType(str, Enum):
    """Supported geospatial file formats."""
    SHAPEFILE = "Shapefile"
    KML = "KML"


class FileResponse(BaseModel):
    """Schema representing file information.

    Complies with the example specified in the problem statement:
    {
        "id": "abc123",
        "filename": "survey.kml",
        "feature_count": 120,
        "crs": "EPSG:4326",
        "status": "COMPLETED"
    }
    """
    id: str = Field(..., description="Unique identifier for the uploaded file")
    filename: str = Field(..., description="Original name of the uploaded file")
    feature_count: int = Field(0, description="Total number of geospatial features extracted")
    crs: str = Field(..., description="Coordinate Reference System identified (e.g. EPSG:4326)")
    status: FileStatus = Field(..., description="Processing status of the file")
    file_type: Optional[FileType] = Field(None, description="Detected format type")
    uploaded_at: Optional[datetime] = Field(None, description="Timestamp when file was uploaded")
    error_message: Optional[str] = Field(None, description="Error details if processing failed")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "abc123",
                "filename": "survey.kml",
                "feature_count": 120,
                "crs": "EPSG:4326",
                "status": "COMPLETED",
                "file_type": "KML",
            }
        }
    )
