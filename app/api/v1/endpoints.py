"""API endpoints for geospatial file upload, status check, and measurement retrieval."""

import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.config import settings
from app.schemas.file import FileResponse, FileStatus, FileType
from app.schemas.measurement import FileMeasurementsResponse
from app.services.measurement_service import MeasurementService
from app.services.parsers.kml_parser import KMLParser
from app.services.parsers.shapefile_parser import ShapefileParser
from app.services.storage import storage_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["Geospatial Files"])


@router.post(
    "/",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a geospatial file",
    description="Upload a .kml file or a .zip archive containing an ESRI Shapefile. "
                "The server automatically parses features and calculates projected metric measurements.",
)
async def upload_geospatial_file(file: UploadFile = File(...)):
    """Upload and process a geospatial file (.zip Shapefile or .kml)."""
    filename = file.filename or "unknown"
    suffix = Path(filename).suffix.lower()

    # Validate file extension
    if suffix not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file format '{suffix}'. "
                f"Allowed formats are .kml or .zip (containing an ESRI Shapefile)."
            ),
        )

    # Generate unique file ID
    file_id = uuid.uuid4().hex[:12]
    target_dir = settings.UPLOAD_DIR / file_id
    target_dir.mkdir(parents=True, exist_ok=True)
    saved_file_path = target_dir / filename

    # Stream file to disk and validate size
    total_size = 0
    try:
        with open(saved_file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                total_size += len(chunk)
                if total_size > settings.MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_BYTES / (1024*1024):.0f}MB",
                    )
                buffer.write(chunk)
    except HTTPException:
        shutil.rmtree(target_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(target_dir, ignore_errors=True)
        logger.error("Failed to write uploaded file to disk: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded file.",
        )
    finally:
        await file.close()

    # Determine file type & parser
    if suffix == ".kml":
        file_type = FileType.KML
        parser = KMLParser()
    else:
        file_type = FileType.SHAPEFILE
        parser = ShapefileParser()

    # Initial file record
    now = datetime.now(timezone.utc)
    file_record = {
        "id": file_id,
        "filename": filename,
        "feature_count": 0,
        "crs": settings.DEFAULT_CRS,
        "status": FileStatus.PROCESSING.value,
        "file_type": file_type.value,
        "uploaded_at": now.isoformat(),
        "error_message": None,
    }
    storage_repo.save_file(file_record)

    # Process and measure
    try:
        dataset = parser.parse(saved_file_path)

        # Calculate measurements with CRS reprojection
        measurements_result = MeasurementService.process_dataset(file_id, filename, dataset)

        # Update record with success
        file_record["feature_count"] = dataset.feature_count
        file_record["crs"] = dataset.crs
        file_record["status"] = FileStatus.COMPLETED.value
        storage_repo.save_file(file_record)

        # Store measurements
        storage_repo.save_measurements(file_id, measurements_result.model_dump())

        logger.info(
            "Successfully processed file %s (%s) with %d features.",
            file_id,
            filename,
            dataset.feature_count,
        )
        return FileResponse(**file_record)

    except ValueError as ve:
        logger.warning("Validation error processing file %s: %s", file_id, ve)
        file_record["status"] = FileStatus.FAILED.value
        file_record["error_message"] = str(ve)
        storage_repo.save_file(file_record)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Geospatial processing error: {ve}",
        )
    except Exception as ex:
        logger.exception("Unexpected error processing file %s: %s", file_id, ex)
        file_record["status"] = FileStatus.FAILED.value
        file_record["error_message"] = str(ex)
        storage_repo.save_file(file_record)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the geospatial file: {ex}",
        )


@router.get(
    "/{id}/",
    response_model=FileResponse,
    summary="Get file processing information",
    description="Returns metadata, processing status, feature count, and CRS for the uploaded file.",
)
async def get_file_info(id: str):
    """Retrieve file information and status by file ID."""
    file_record = storage_repo.get_file(id)
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with id '{id}' not found.",
        )
    return FileResponse(**file_record)


@router.get(
    "/{id}/measurements/",
    response_model=FileMeasurementsResponse,
    summary="Get calculated measurements for the file",
    description="Returns measurement values (area, length, perimeter) for each feature along with GeoJSON geometry and aggregate summary.",
)
async def get_file_measurements(id: str):
    """Retrieve measurements for all features in the uploaded file."""
    file_record = storage_repo.get_file(id)
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with id '{id}' not found.",
        )

    if file_record["status"] == FileStatus.FAILED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File processing failed: {file_record.get('error_message')}",
        )

    if file_record["status"] == FileStatus.PROCESSING.value:
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail="File is currently being processed. Please retry shortly.",
        )

    measurements_data = storage_repo.get_measurements(id)
    if not measurements_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Measurements not available for file '{id}'.",
        )

    return FileMeasurementsResponse(**measurements_data)


@router.get(
    "/",
    response_model=List[FileResponse],
    summary="List all uploaded files",
    description="Returns a list of all uploaded geospatial files and their current processing status.",
)
async def list_files():
    """List all tracked geospatial files."""
    records = storage_repo.list_files()
    return [FileResponse(**rec) for rec in records]


@router.delete(
    "/{id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an uploaded file",
    description="Deletes the file, its associated measurements, and stored files from disk.",
)
async def delete_file(id: str):
    """Delete a geospatial file by ID."""
    deleted = storage_repo.delete_file(id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with id '{id}' not found.",
        )
    return None
