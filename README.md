# Geospatial File Measurement API

A FastAPI backend service that takes geospatial files (`.zip` Shapefiles and `.kml` files), extracts geographic features, reprojects coordinates to an appropriate local metric system, and calculates accurate measurements like area and length.

Built with Python 3.10, FastAPI, Shapely, and Pyproj.

---

## What this project does

When working with geospatial data, files often store coordinates in latitude and longitude degrees (such as `EPSG:4326` / WGS 84). Calculating area or distance directly on degrees doesn't give real physical units because the Earth is curved and degrees get smaller as you move away from the equator.

This API handles that automatically:
1. Accepts an uploaded `.zip` containing a Shapefile or a `.kml` file.
2. Reads the features, geometry types, and attributes.
3. Automatically finds the right local **UTM (Universal Transverse Mercator) zone** based on where the feature is located on Earth.
4. Reprojects the coordinates into meters.
5. Calculates real-world measurements:
   - **Polygons**: Area (in $m^2$, hectares, and $km^2$) + perimeter.
   - **LineStrings**: Length (in meters and kilometers).
   - **Points**: Handled gracefully without errors (no measurement needed).
6. Provides an interactive Leaflet map dashboard to visually inspect the uploaded files and measurements.

---

## Quick Start / Setup

### Prerequisites
- Python 3.10+
- Git

### 1. Clone and navigate to the project
```bash
git clone https://github.com/Harsha200621/geospatial-measurement-api.git
cd geospatial-measurement-api
```

### 2. Set up virtual environment
On Windows (PowerShell):
```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

On macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the server
```bash
uvicorn app.main:app --reload
```

Once running, you can open:
- **Interactive Map Dashboard**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Swagger API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## How to Test

Run the automated test suite:
```bash
pytest -v
```
All 22 unit and integration tests run in under a second.

You can also run the quick end-to-end verification script:
```bash
python scripts/verify_e2e.py
```

---

## API Endpoints

### 1. Upload File
`POST /api/files/`

Uploads and processes a `.zip` (Shapefile) or `.kml` file.

**curl example:**
```bash
curl -X POST "http://127.0.0.1:8000/api/files/" -F "file=@samples/sample_survey.kml"
```

**Response (201 Created):**
```json
{
  "id": "f32b96d87a7b",
  "filename": "sample_survey.kml",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "file_type": "KML"
}
```

---

### 2. Get File Information
`GET /api/files/{id}/`

Returns basic information and status for an uploaded file.

**Response (200 OK):**
```json
{
  "id": "f32b96d87a7b",
  "filename": "sample_survey.kml",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

---

### 3. Get Measurements
`GET /api/files/{id}/measurements/`

Returns detailed measurements for every feature in the file, along with an overall summary and GeoJSON geometry.

**Response (200 OK):**
```json
{
  "id": "f32b96d87a7b",
  "filename": "sample_survey.kml",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "summary": {
    "total_area_sq_meters": 300430.08,
    "total_area_hectares": 30.04,
    "total_length_meters": 775.22,
    "total_length_km": 0.77,
    "polygon_count": 1,
    "linestring_count": 1,
    "point_count": 1,
    "unsupported_count": 0
  },
  "features": [
    {
      "feature_id": "feature_001",
      "geometry_type": "Polygon",
      "crs": "EPSG:4326",
      "projected_crs": "EPSG:32643",
      "properties": {
        "name": "Agricultural Field 1",
        "crop_type": "Paddy"
      },
      "measurements": {
        "area_sq_meters": 300430.08,
        "area_hectares": 30.04,
        "length_meters": 2192.56,
        "note": "Area and perimeter calculated via metric projection."
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [...]
      },
      "status": "PROCESSED"
    }
  ]
}
```

---

## Project Structure

```text
Aereo/
├── app/
│   ├── main.py                     # FastAPI app, lifespan, CORS, and routes
│   ├── config.py                   # App settings (upload directory, size limits)
│   ├── api/v1/
│   │   ├── router.py               # Route aggregation
│   │   └── endpoints.py            # Upload, info, and measurement routes
│   ├── schemas/
│   │   ├── file.py                 # Pydantic schemas for file responses
│   │   └── measurement.py          # Pydantic schemas for measurements & summary
│   ├── services/
│   │   ├── storage.py              # In-memory repository with JSON file persistence
│   │   ├── crs_service.py          # Automatic UTM projection and coordinate transform
│   │   ├── measurement_service.py  # Area/length calculations and aggregation
│   │   └── parsers/
│   │       ├── base.py             # Base parser interface
│   │       ├── shapefile_parser.py # Reads .zip shapefiles safely
│   │       └── kml_parser.py       # Reads KML Placemarks (Polygon, Line, Point)
│   └── static/
│       └── index.html              # Interactive Leaflet map dashboard
├── samples/                        # Sample KML and Shapefile .zip for testing
├── scripts/
│   ├── generate_samples.py         # Generates test files
│   └── verify_e2e.py               # Quick end-to-end test script
├── tests/                          # Automated pytest suite (22 tests)
├── requirements.txt
└── README.md
```

---

## Architecture & How It Works

### 1. File Upload & Ingestion
When a file is uploaded:
- The file extension is checked (`.zip` or `.kml`).
- The file is streamed to a temporary directory on disk (with size checks to avoid memory exhaustion).
- If it's a `.zip`, we safely extract its contents with path validation to protect against **Zip Slip** directory traversal attacks.
- We locate the primary `.shp` and check for an accompanying `.prj` file to read the coordinate system.

### 2. CRS Handling Strategy
Why not calculate directly?
- If coordinates are in degrees (like `EPSG:4326`), 1 degree at the equator is ~111 km, but near 60° latitude it's only ~55 km. Direct degree calculations produce inaccurate distorted numbers.

Our approach:
- We calculate the centroid (center point) of each geometry.
- We determine which **Universal Transverse Mercator (UTM)** zone it falls into using its longitude:
  `zone = int((longitude + 180) / 6) + 1`
- If latitude is in the northern hemisphere, we use `EPSG:32600 + zone` (e.g., Bangalore at 77.58°E, 12.96°N falls in Zone 43N -> `EPSG:32643`).
- If latitude is in the southern hemisphere, we use `EPSG:32700 + zone`.
- We reproject using `pyproj` with `always_xy=True` so that longitude and latitude never get swapped by mistake.
- If a file is already in a projected metric coordinate system, we keep the original projection.

### 3. Measurement Calculation
Once geometries are in meters:
- **Polygons**: `projected_geom.area` gives area in square meters. We also compute hectares ($m^2 / 10000$) and square kilometers.
- **LineStrings**: `projected_geom.length` gives length in meters and kilometers.
- **Points**: Have zero area and length, so they are marked as `NOT_MEASURED` with a helpful note.
- **Unsupported Geometries**: Logged and marked `UNSUPPORTED` without crashing the service.

---

## Technical Design Decisions

1. **FastAPI over Django REST Framework**:
   FastAPI was chosen because it is lightweight, runs asynchronously, provides automatic interactive documentation (`/docs`), and handles request validation cleanly via Pydantic v2.
2. **PyShp (`shapefile`) instead of GDAL/Fiona**:
   GDAL and Fiona require heavy C/C++ system libraries that frequently cause complex installation and build issues on developer machines (especially on Windows). `pyshp` is pure Python, reliable, and easily handles standard Shapefile extraction.
3. **Dynamic Centroid UTM instead of Web Mercator**:
   Web Mercator (`EPSG:3857`) has major scale distortion that exaggerates area significantly as you move away from the equator. Local UTM zones keep scale distortion below 0.1%, making it ideal for aerial and drone survey measurements.
4. **Interactive Leaflet UI Dashboard**:
   Although only a backend API was required, adding a simple single-page Leaflet dashboard lets anyone quickly test the API with real files visually without needing Postman or terminal commands.

---

## What I Learned

- **Coordinate Axis Order Pitfall**: In PROJ 6+, geographic CRS definitions standardise on `(latitude, longitude)`, while GeoJSON and Shapely expect `(x, y)` which is `(longitude, latitude)`. Using `always_xy=True` in `pyproj.Transformer` was necessary to avoid accidentally swapping coordinates.
- **KML Namespace Variations**: Different GIS software (Google Earth, QGIS) export KML with slightly different XML namespaces. Writing a namespace-agnostic tag finder made the parser much more resilient.
- **ESRI Shapefile Ring Order**: In shapefiles, outer polygon rings must be ordered clockwise, while inner holes are counter-clockwise. Ensuring correct orientation prevents geometries from being misinterpreted as holes.

---

## Future Improvements

- **Async Task Queue**: For huge files with hundreds of thousands of vertices, offload parsing to Celery / Redis background workers so the API remains immediately responsive.
- **Database Persistence**: Add PostgreSQL with PostGIS for spatial indexing ($R$-tree) and spatial queries (bounding box filters, polygon intersections).
- **GeoJSON Export**: Add a download endpoint (`GET /api/files/{id}/export?format=geojson`) to export the measured features directly into desktop GIS tools like QGIS.
- **Cloud Storage**: Store uploaded files in Amazon S3 or Google Cloud Storage instead of the local filesystem for cloud deployment.
