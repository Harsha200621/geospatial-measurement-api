"""Thread-safe storage repository for geospatial file records and measurement data."""

import json
import logging
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class FileStorageRepository:
    """In-memory and file-backed repository for managing file records and measurements.

    Uses a reentrant lock (RLock) to ensure concurrency safety across concurrent API requests.
    Optionally persists metadata to disk to survive application restarts.
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        self._lock = RLock()
        self._storage_dir = storage_dir or settings.UPLOAD_DIR
        self._files: Dict[str, Dict[str, Any]] = {}
        self._measurements: Dict[str, Dict[str, Any]] = {}
        self._load_persisted_records()

    def _get_metadata_path(self, file_id: str) -> Path:
        return self._storage_dir / file_id / "metadata.json"

    def _load_persisted_records(self) -> None:
        """Scan storage directory on startup to restore previously processed records."""
        try:
            if not self._storage_dir.exists():
                return
            for item in self._storage_dir.iterdir():
                if item.is_dir():
                    meta_path = item / "metadata.json"
                    if meta_path.exists():
                        with open(meta_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            file_id = data.get("file_info", {}).get("id")
                            if file_id:
                                self._files[file_id] = data.get("file_info", {})
                                if "measurements" in data:
                                    self._measurements[file_id] = data["measurements"]
            logger.info("Loaded %d existing geospatial file records from storage.", len(self._files))
        except Exception as e:
            logger.warning("Failed to restore persisted records: %s", e)

    def _persist_record_to_disk(self, file_id: str) -> None:
        """Persist in-memory state of a record to disk as JSON."""
        try:
            target_dir = self._storage_dir / file_id
            target_dir.mkdir(parents=True, exist_ok=True)
            meta_path = self._get_metadata_path(file_id)

            data = {
                "file_info": self._files.get(file_id, {}),
                "measurements": self._measurements.get(file_id, {}),
            }

            # Serialize datetime objects
            def json_serializer(obj: Any) -> Any:
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")

            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(data, f, default=json_serializer, indent=2)
        except Exception as e:
            logger.error("Failed to persist file record %s to disk: %s", file_id, e)

    def save_file(self, file_record: Dict[str, Any]) -> None:
        """Insert or update a file record."""
        with self._lock:
            file_id = file_record["id"]
            self._files[file_id] = file_record
            self._persist_record_to_disk(file_id)

    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve file information by ID."""
        with self._lock:
            return self._files.get(file_id)

    def save_measurements(self, file_id: str, measurements_data: Dict[str, Any]) -> None:
        """Save measurement calculations for a given file ID."""
        with self._lock:
            self._measurements[file_id] = measurements_data
            self._persist_record_to_disk(file_id)

    def get_measurements(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve calculated measurements by file ID."""
        with self._lock:
            return self._measurements.get(file_id)

    def list_files(self) -> List[Dict[str, Any]]:
        """List all tracked file records."""
        with self._lock:
            return list(self._files.values())

    def delete_file(self, file_id: str) -> bool:
        """Delete file and its associated measurements."""
        with self._lock:
            found = file_id in self._files
            if found:
                del self._files[file_id]
                self._measurements.pop(file_id, None)
                record_dir = self._storage_dir / file_id
                if record_dir.exists():
                    import shutil
                    shutil.rmtree(record_dir, ignore_errors=True)
            return found


# Global singleton instance of repository
storage_repo = FileStorageRepository()
