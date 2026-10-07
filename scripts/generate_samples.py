"""Script to generate valid geospatial sample files (KML and zipped Shapefile) for testing."""

import sys
import tempfile
import zipfile
from pathlib import Path

# Ensure UTF-8 console output for non-ASCII path characters on Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import shapefile

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


def create_sample_kml():
    """Create a sample KML file with Polygon, LineString, and Point features."""
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Sample Drone Survey</name>
    <description>Demonstration survey containing Polygon, LineString, and Point</description>
    
    <!-- Polygon: Survey Farm Plot -->
    <Placemark id="feature_001">
      <name>Agricultural Field 1</name>
      <description>Rice cultivation field boundary</description>
      <ExtendedData>
        <Data name="crop_type"><value>Paddy</value></Data>
        <Data name="surveyor"><value>Aereo Drone Team</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.58000,12.96000,0.0
              77.58500,12.96000,0.0
              77.58500,12.96500,0.0
              77.58000,12.96500,0.0
              77.58000,12.96000,0.0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>

    <!-- LineString: Drone Flight Path -->
    <Placemark id="feature_002">
      <name>Flight Trajectory Alpha</name>
      <description>Aerial inspection transect line</description>
      <ExtendedData>
        <Data name="altitude_agl_m"><value>100</value></Data>
        <Data name="speed_m_s"><value>12.5</value></Data>
      </ExtendedData>
      <LineString>
        <coordinates>
          77.58000,12.96000,100.0
          77.58250,12.96250,100.0
          77.58500,12.96500,100.0
        </coordinates>
      </LineString>
    </Placemark>

    <!-- Point: Ground Control Point (GCP) -->
    <Placemark id="feature_003">
      <name>GCP 01</name>
      <description>Ground control reference station</description>
      <ExtendedData>
        <Data name="accuracy_cm"><value>1.2</value></Data>
      </ExtendedData>
      <Point>
        <coordinates>
          77.58250,12.96250,910.0
        </coordinates>
      </Point>
    </Placemark>

  </Document>
</kml>
"""
    kml_path = SAMPLES_DIR / "sample_survey.kml"
    with open(kml_path, "w", encoding="utf-8") as f:
        f.write(kml_content)
    print(f"Created sample KML at {kml_path}")


def create_sample_shapefile_zip():
    """Create a sample ESRI Shapefile inside a zip archive."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        base_name = "cadastral_survey"
        shp_file = temp_path / f"{base_name}.shp"

        # Create Shapefile with Polygon shapes
        w = shapefile.Writer(str(temp_path / base_name), shapeType=shapefile.POLYGON)
        w.field("PLOT_NAME", "C", size=50)
        w.field("ZONE", "C", size=20)
        w.field("SURVEY_ID", "N", size=10)

        # Feature 1: Polygon
        poly1_coords = [
            [
                [77.5900, 12.9700],
                [77.5950, 12.9700],
                [77.5950, 12.9750],
                [77.5900, 12.9750],
                [77.5900, 12.9700],
            ]
        ]
        w.poly(poly1_coords)
        w.record(PLOT_NAME="Commercial Zone A", ZONE="Urban", SURVEY_ID=101)

        # Feature 2: Polygon
        poly2_coords = [
            [
                [77.5960, 12.9700],
                [77.6000, 12.9700],
                [77.6000, 12.9740],
                [77.5960, 12.9740],
                [77.5960, 12.9700],
            ]
        ]
        w.poly(poly2_coords)
        w.record(PLOT_NAME="Residential Plot B", ZONE="Suburban", SURVEY_ID=102)

        w.close()

        # Write WGS 84 .prj file (OGC WKT format)
        prj_wkt = (
            'GEOGCS["GCS_WGS_1984",'
            'DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],'
            'PRIMEM["Greenwich",0],'
            'UNIT["Degree",0.017453292519943295]]'
        )
        prj_file = temp_path / f"{base_name}.prj"
        with open(prj_file, "w", encoding="utf-8") as f:
            f.write(prj_wkt)

        # Bundle into zip
        zip_output = SAMPLES_DIR / "sample_shapefile.zip"
        with zipfile.ZipFile(zip_output, "w", zipfile.ZIP_DEFLATED) as zf:
            for ext in [".shp", ".shx", ".dbf", ".prj"]:
                f_path = temp_path / f"{base_name}{ext}"
                if f_path.exists():
                    zf.write(f_path, arcname=f_path.name)

        print(f"Created sample Shapefile archive at {zip_output}")


if __name__ == "__main__":
    create_sample_kml()
    create_sample_shapefile_zip()
