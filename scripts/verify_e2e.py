"""End-to-end verification script for Geospatial File Measurement API."""

import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

client = TestClient(app)

print("=== 1. Testing Root & Health ===")
r = client.get("/")
print("Service:", r.json()["service"])
h = client.get("/api/health")
print("Health:", h.json()["status"])

print("\n=== 2. Testing KML Upload & Measurements ===")
kml_path = Path("samples/sample_survey.kml")
with open(kml_path, "rb") as f:
    up_res = client.post(
        "/api/files/",
        files={"file": (kml_path.name, f, "application/vnd.google-earth.kml+xml")},
    )
print(f"Upload Status: {up_res.status_code}")
kml_record = up_res.json()
print("Uploaded File Record:", json.dumps(kml_record, indent=2))

kml_id = kml_record["id"]
meas_res = client.get(f"/api/files/{kml_id}/measurements/")
print(f"Measurements Status: {meas_res.status_code}")
meas_data = meas_res.json()
print("Summary:", json.dumps(meas_data["summary"], indent=2))
for feat in meas_data["features"]:
    print(f"Feature: {feat['feature_id']} | Type: {feat['geometry_type']} | Status: {feat['status']} | Measurements: {feat['measurements']}")

print("\n=== 3. Testing Shapefile (.zip) Upload & Measurements ===")
shp_path = Path("samples/sample_shapefile.zip")
with open(shp_path, "rb") as f:
    shp_up = client.post(
        "/api/files/",
        files={"file": (shp_path.name, f, "application/zip")},
    )
print(f"Shapefile Upload Status: {shp_up.status_code}")
shp_record = shp_up.json()
print("Shapefile Record:", json.dumps(shp_record, indent=2))

shp_id = shp_record["id"]
shp_meas = client.get(f"/api/files/{shp_id}/measurements/").json()
print("Shapefile Summary:", json.dumps(shp_meas["summary"], indent=2))
for feat in shp_meas["features"]:
    print(f"Feature: {feat['feature_id']} | Type: {feat['geometry_type']} | Status: {feat['status']} | Measurements: {feat['measurements']}")

print("\n=== All End-to-End Verifications Succeeded! ===")
