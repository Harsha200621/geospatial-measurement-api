# Geospatial File Measurement API

A FastAPI backend service that accepts geospatial files (Shapefile `.zip` or `.kml`), processes the features, and calculates geometric measurements like area and length.

---

## 1. Setup

### Requirements
- Python 3.10+
- Git

### Run Locally

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Harsha200621/geospatial-measurement-api.git
   cd geospatial-measurement-api
   ```

2. **Create and activate a virtual environment:**
   - **Windows:**
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - **Linux / Mac:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Start the application:**
   ```bash
   uvicorn app.main:app --reload
   ```

- **Interactive API Docs (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Interactive Map UI:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

### Run Tests
```bash
pytest
```

---

## 2. API Documentation

### Upload File
- **Endpoint:** `POST /api/files/`
- **Content-Type:** `multipart/form-data`
- **Body:** `file` (.kml or .zip Shapefile)

**Example Request:**
```bash
curl -X POST "http://127.0.0.1:8000/api/files/" -F "file=@samples/sample_survey.kml"
```

**Example Response:**
```json
{
  "id": "abc123456789",
  "filename": "survey.kml",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

---

### File Information
- **Endpoint:** `GET /api/files/{id}/`

**Example Request:**
```bash
curl -X GET "http://127.0.0.1:8000/api/files/abc123456789/"
```

**Example Response:**
```json
{
  "id": "abc123456789",
  "filename": "survey.kml",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

---

### Measurements
- **Endpoint:** `GET /api/files/{id}/measurements/`

**Example Request:**
```bash
curl -X GET "http://127.0.0.1:8000/api/files/abc123456789/measurements/"
```

**Example Response:**
```json
{
  "id": "abc123456789",
  "filename": "survey.kml",
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
        "name": "Field A"
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
    },
    {
      "feature_id": "feature_002",
      "geometry_type": "Point",
      "crs": "EPSG:4326",
      "projected_crs": null,
      "properties": {},
      "measurements": {
        "area_sq_meters": null,
        "length_meters": null,
        "note": "No measurement required for Point geometry."
      },
      "geometry": {
        "type": "Point",
        "coordinates": [77.58, 12.96]
      },
      "status": "NOT_MEASURED"
    }
  ]
}
```

---

## 3. Architecture

### Application Structure
```text
Aereo/
├── app/
│   ├── main.py                     # FastAPI entry point & routes
│   ├── config.py                   # App settings (file limits, paths)
│   ├── api/v1/endpoints.py         # API endpoints (upload, info, measurements)
│   ├── schemas/                    # Pydantic models (file & measurement schemas)
│   ├── services/
│   │   ├── crs_service.py          # CRS projection & UTM calculation
│   │   ├── measurement_service.py  # Area & length calculations
│   │   ├── storage.py              # In-memory and file-backed repository
│   │   └── parsers/
│   │       ├── shapefile_parser.py # Reads .zip shapefiles
│   │       └── kml_parser.py       # Reads .kml XML files
│   └── static/index.html           # Leaflet map UI
├── samples/                        # Sample KML and Shapefile .zip
├── tests/                          # 22 automated unit and integration tests
├── requirements.txt
└── README.md
```

### File-Processing Flow
1. Client uploads `.zip` or `.kml` via `POST /api/files/`.
2. Extension and size are validated.
3. The file is parsed:
   - For `.zip`: Safely extracts files and uses PyShp to read `.shp`, `.dbf`, and `.prj`.
   - For `.kml`: Uses XML ElementTree to extract Placemarks and coordinates.
4. Features, attributes, and geometries are loaded into standard objects.

### Measurement Calculation Flow
1. For each feature, check its geometry type:
   - **Polygon / MultiPolygon:** Compute area ($m^2$, hectares) and perimeter length ($m$).
   - **LineString / MultiLineString:** Compute length ($m$, $km$).
   - **Point / MultiPoint:** Mark as `NOT_MEASURED` (no calculation needed).
   - **Other / Invalid:** Handled gracefully and marked as `UNSUPPORTED` without crashing.
2. An overall summary is computed aggregating total area, length, and feature counts.

### CRS Handling
- Most input files use geographic coordinates (latitude and longitude in degrees, like `EPSG:4326`).
- Calculating area or length directly on degrees is inaccurate because degree lengths vary depending on latitude.
- **Strategy:** We compute the centroid (center) of the geometry and automatically select its local **Universal Transverse Mercator (UTM)** zone:
  $$\text{UTM Zone} = \text{int}((\text{lon} + 180) / 6) + 1$$
- For the northern hemisphere: `EPSG:32600 + zone`.
- For the southern hemisphere: `EPSG:32700 + zone`.
- We reproject using `pyproj` with `always_xy=True` (to guarantee longitude/latitude order) before measuring.
- If the file is already in a metric projected CRS, that CRS is kept.

---

## 4. Design Decisions

- **FastAPI over Django:** FastAPI is lightweight, fast, has native async support, and automatically generates interactive Swagger documentation.
- **PyShp over GDAL/Fiona:** GDAL requires complex C/C++ system libraries that are difficult to install across different operating systems (especially Windows). `pyshp` is pure Python, reliable, and has zero external C dependencies.
- **Dynamic UTM over Web Mercator:** Web Mercator (`EPSG:3857`) heavily distorts areas away from the equator. Local UTM zones keep distortion under 0.1%, giving accurate real-world measurements.
- **Zip-Slip Protection:** When extracting uploaded `.zip` archives, paths are strictly validated to prevent directory traversal attacks.

---

## 5. Learnings & Future Improvements

### Learnings
- **Coordinate Order:** `pyproj` requires `always_xy=True` to ensure coordinate order stays as `(x, y)` / `(lon, lat)` and avoids inadvertent coordinate flipping.
- **KML Namespaces:** KML files often use different XML namespaces depending on the exporting software (Google Earth, QGIS). Writing namespace-tolerant parsing ensures high compatibility.
- **Shapefile Ring Orientation:** ESRI Shapefiles require exterior rings to be clockwise and inner rings to be counter-clockwise. Following this rule ensures polygons don't get treated as holes.

### Future Improvements
- **Background Task Queue:** Use Celery or Redis for very large files with hundreds of thousands of vertices.
- **Spatial Database:** Use PostGIS for storing features with spatial indexing ($R$-tree) and bounding box queries.
- **GeoJSON Export:** Add an endpoint to export processed measurements directly as a downloadable GeoJSON file for QGIS.
