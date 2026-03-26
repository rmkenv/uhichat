import ee
import streamlit as st
from google.oauth2 import service_account


def clean_pem_key(key):
    """
    Rips out common copy-paste artifacts that cause 'InvalidByte' errors.
    """
    if not key:
        return None

    # 1. Remove literal '\n' text strings and replace with real newlines
    key = key.replace("\\n", "\n")

    # 2. Remove any accidental whitespace or invisible characters at start/end
    key = key.strip()

    # 3. Ensure the PEM boundaries are clean
    header = "-----BEGIN PRIVATE KEY-----"
    footer = "-----END PRIVATE KEY-----"

    # Strip existing headers to re-standardize (prevents double-headers)
    inner_content = key.replace(header, "").replace(footer, "").strip()

    # Re-build the key with perfect formatting
    standardized_key = f"{header}\n{inner_content}\n{footer}\n"

    return standardized_key


def initialize_ee():
    """
    Initializes Earth Engine with a robust authentication flow.
    Safely handles the case where EE is already initialized.
    """
    # Try a lightweight API call to check if already initialized
    try:
        ee.data.getInfo()
        return  # Already initialized, nothing to do
    except Exception:
        pass  # Not yet initialized — proceed below

    try:
        # Check if secrets exist
        if "gee_service_account" not in st.secrets:
            st.error("Missing 'gee_service_account' in Streamlit Secrets!")
            st.stop()

        # Convert Secret object to dict to allow modification
        sa_info = dict(st.secrets["gee_service_account"])

        # Clean the private key before passing to Google Auth
        sa_info["private_key"] = clean_pem_key(sa_info["private_key"])

        # Create credentials
        credentials = service_account.Credentials.from_service_account_info(sa_info)

        # Use GCP_PROJECT_ID from secrets if present, otherwise fall back to
        # the service account's own project_id (raise KeyError if missing)
        project_id = st.secrets.get("GCP_PROJECT_ID") or sa_info["project_id"]

        ee.Initialize(credentials=credentials, project=project_id)

    except Exception as e:
        st.error(f"Failed to initialize Earth Engine: {e}")
        st.info("Check if your Secret 'private_key' was copied completely from the JSON file.")
        st.stop()


def get_gee_data(city_name: str, lon: float, lat: float):
    """
    Fetches and processes 20-year climate trends and 30m thermal data.

    Parameters
    ----------
    city_name : str
        Human-readable label used only for display purposes.
    lon : float
        Longitude of the city center (decimal degrees).
    lat : float
        Latitude of the city center (decimal degrees).

    Returns
    -------
    aoi, current_lst, forecast_2030, stats, thumb_url
        Returns a tuple of (None, None, None, None, None) on failure.
    """
    initialize_ee()

    try:
        # 1. Define Area of Interest from explicit coordinates
        #    (avoids unreliable ee.Algorithms.Geocoding.geometry())
        aoi = ee.Geometry.Point([lon, lat]).buffer(5000).bounds()

        # 2. Historical Trend (MODIS LST 1km, 2003–2026)
        years = ee.List.sequence(2003, 2026)

        def calculate_annual_temp(y):
            start = ee.Date.fromYMD(y, 6, 1)
            return (
                ee.ImageCollection("MODIS/061/MYD11A2")
                .filterBounds(aoi)
                .filterDate(start, start.advance(3, "month"))
                .select("LST_Day_1km")
                .mean()
                .multiply(0.02)
                .subtract(273.15)
                .multiply(1.8)
                .add(32)
                .set("year", y)
            )

        modis_col = ee.ImageCollection(years.map(calculate_annual_temp))

        # Sen's Slope over the time series
        trend = modis_col.reduce(ee.Reducer.sensSlope()).select("slope")

        # 3. Current High-Res Baseline (Landsat 8/9, 30m)
        #    End date is exclusive in EE, so use 2027-01-01 to include all of 2026
        current_lst = (
            ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
            .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2"))
            .filterBounds(aoi)
            .filterDate("2024-01-01", "2027-01-01")
            .filter(ee.Filter.lt("CLOUD_COVER", 15))
            .median()
            .select("ST_B10")
            .multiply(0.00341802)
            .add(149)
            .subtract(273.15)
            .multiply(1.8)
            .add(32)
            .clip(aoi)
        )

        # 4. 2030 Prediction (Current + Trend × 4 remaining years)
        #    Resample trend from 1km → 30m before adding
        forecast_2030 = current_lst.add(
            trend.resample("bilinear").reproject(
                crs=current_lst.projection(), scale=30
            ).multiply(4)
        ).rename("ST_B10")

        # 5. Package statistics for Gemini reasoning
        stats = {
            "city": city_name,
            "mean_temp_f": current_lst.reduceRegion(
                ee.Reducer.mean(), aoi, 30
            ).getInfo().get("ST_B10"),
            "warming_trend_f_per_year": trend.reduceRegion(
                ee.Reducer.mean(), aoi, 1000
            ).getInfo().get("slope"),
            "max_hotspot_f": current_lst.reduceRegion(
                ee.Reducer.max(), aoi, 30
            ).getInfo().get("ST_B10"),
        }

        # 6. Generate static thumbnail for Gemini Vision
        vis = {
            "min": 80,
            "max": 115,
            "palette": ["blue", "yellow", "red"],
            "dimensions": 512,
            "region": aoi,
        }
        thumb_url = current_lst.getThumbURL(vis)

        return aoi, current_lst, forecast_2030, stats, thumb_url

    except Exception as e:
        st.error(f"Geospatial Processing Error: {e}")
        return None, None, None, None, None
