"""Integration tests for FastAPI endpoints."""

from pathlib import Path
from fastapi.testclient import TestClient


def test_root_and_health_endpoints(client: TestClient):
    """Test root and health check endpoints."""
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["status"] == "online"

    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"


def test_upload_kml_file_success(client: TestClient, sample_kml_path: Path):
    """Test POST /api/files/ with valid KML file."""
    with open(sample_kml_path, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": (sample_kml_path.name, f, "application/vnd.google-earth.kml+xml")},
        )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["filename"] == "sample_survey.kml"
    assert data["feature_count"] == 3
    assert data["crs"] == "EPSG:4326"
    assert data["status"] == "COMPLETED"

    # Verify GET /api/files/{id}/
    file_id = data["id"]
    get_res = client.get(f"/api/files/{file_id}/")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == file_id
    assert get_res.json()["feature_count"] == 3

    # Verify GET /api/files/{id}/measurements/
    meas_res = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_res.status_code == 200
    meas_data = meas_res.json()
    assert meas_data["id"] == file_id
    assert len(meas_data["features"]) == 3
    assert meas_data["summary"]["polygon_count"] == 1
    assert meas_data["summary"]["linestring_count"] == 1
    assert meas_data["summary"]["point_count"] == 1
    assert meas_data["summary"]["total_area_sq_meters"] > 0
    assert meas_data["summary"]["total_length_meters"] > 0


def test_upload_shapefile_zip_success(client: TestClient, sample_shapefile_path: Path):
    """Test POST /api/files/ with valid Shapefile zip archive."""
    with open(sample_shapefile_path, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": (sample_shapefile_path.name, f, "application/zip")},
        )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["filename"] == "sample_shapefile.zip"
    assert data["feature_count"] == 2
    assert data["status"] == "COMPLETED"

    file_id = data["id"]
    meas_res = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_res.status_code == 200
    meas_data = meas_res.json()
    assert meas_data["summary"]["polygon_count"] == 2
    assert meas_data["summary"]["total_area_sq_meters"] > 0


def test_upload_invalid_extension(client: TestClient):
    """Test uploading an unsupported file format (.txt) returns 400 Bad Request."""
    response = client.post(
        "/api/files/",
        files={"file": ("notes.txt", b"Invalid content", "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_get_nonexistent_file(client: TestClient):
    """Test GET /api/files/{id}/ with non-existent ID returns 404."""
    response = client.get("/api/files/nonexistent_id/")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_nonexistent_measurements(client: TestClient):
    """Test GET /api/files/{id}/measurements/ with non-existent ID returns 404."""
    response = client.get("/api/files/nonexistent_id/measurements/")
    assert response.status_code == 404


def test_list_and_delete_file(client: TestClient, sample_kml_path: Path):
    """Test listing files and deleting a file."""
    # Upload a file first
    with open(sample_kml_path, "rb") as f:
        res = client.post(
            "/api/files/",
            files={"file": ("to_delete.kml", f, "application/vnd.google-earth.kml+xml")},
        )
    file_id = res.json()["id"]

    # List files
    list_res = client.get("/api/files/")
    assert list_res.status_code == 200
    assert any(item["id"] == file_id for item in list_res.json())

    # Delete file
    del_res = client.delete(f"/api/files/{file_id}/")
    assert del_res.status_code == 204

    # Verify it is deleted
    get_res = client.get(f"/api/files/{file_id}/")
    assert get_res.status_code == 404
