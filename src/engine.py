import ee
import streamlit as st
import leafmap
from google.oauth2 import service_account

def clean_pem_key(key):
    """Standardizes PEM keys to prevent 'InvalidByte' or decryption errors."""
    if not key: return None
    key = key.replace("\\n", "\n").strip()
    header = "-----BEGIN PRIVATE KEY-----"
    footer = "-----END PRIVATE KEY-----"
    inner = key.replace(header, "").replace(footer, "").strip()
    return f"{header}\n{inner}\n{footer}\n"

def initialize_ee():
    """Initializes Earth Engine with explicit OAuth scopes."""
    if ee.data.is_initialized(): return 

    try:
        sa_info = dict(st.secrets["gee_service_account"])
        ee_scopes = ['https://www.googleapis.com/auth/earthengine']
        sa_info["private_key"] = clean_pem_key(sa_info["private_key"])
        
        credentials = service_account.Credentials.from_service_account_info(
            sa_info, scopes=ee_scopes
        )
        
        project_id = st.secrets.get("GCP_PROJECT_ID") or sa_info.get("project_id")
        ee.Initialize(credentials=credentials, project=project_id)
    except Exception as e:
        st.error(f"Earth Engine Auth Failed: {e}")
        st.stop()

def get_gee_data(city_name: str, lon: float, lat: float):
    """
    Analyzes climate trends with dynamic date detection to handle 
    satellite processing lags and cloud cover.
    """
    initialize_ee()
    try:
        # 1. Define Area of Interest (5km radius)
        aoi = ee.Geometry.Point([lon, lat]).buffer(5000).bounds()

        # 2. DYNAMIC DATE DETECTION (Fixes 'Insufficient Data' error)
        # Find the most recent MODIS image available in the global catalog
        latest_img = ee.ImageCollection("MODIS/061/MYD11A2") \
            .limit(1, "system:time_start", False).first()
        
        # Determine the latest year available (e.g., 2025 or early 2026)
        last_year = ee.Date(latest_img.get("system:time_start")).get("year").getInfo()
        start_year = last_year - 20 # Look back 20 years from today
        
        years = ee.List.sequence(start_year, last_year)
        
        def process_modis_year(y):
            # Target Summer months (June 1 - Aug 31)
            start = ee.Date.fromYMD(y, 6, 1)
            img = ee.ImageCollection("MODIS/061/MYD11A2") \
                .filterBounds(aoi) \
                .filterDate(start, start.advance(3, "month")) \
                .select("LST_Day_1km").mean()
            
            # Tag whether the image actually has data (not empty due to clouds)
            return img.set("year", y).set("has_data", img.bandNames().size().gt(0))

        # 3. Filter & Trend Calculation
        modis_col = ee.ImageCollection(years.map(process_modis_year)) \
            .filter(ee.Filter.eq("has_data", True))

        # Guard: Ensure we have enough data points for a valid regression
        data_count = modis_col.size().getInfo()
        if data_count < 3:
            st.warning(f"⚠️ Only {data_count} years of clear data found for {city_name}. Trends cannot be calculated.")
            return None, None, None, None, None

        # Convert to Fahrenheit
        trend_images = modis_col.map(lambda img: 
            img.multiply(0.02).subtract(273.15).multiply(1.8).add(32))
        
        # Calculate warming slope
        trend = trend_images.reduce(ee.Reducer.sensSlope()).select("slope")

        # 4. CURRENT HIGH-RES (Landsat 8/9)
        # Use a 3-year window to ensure at least one cloud-free median image
        landsat_col = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2") \
            .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")) \
            .filterBounds(aoi) \
            .filterDate("2023-01-01", "2027-01-01") \
            .filter(ee.Filter.lt("CLOUD_COVER", 40))

        if landsat_col.size().getInfo() == 0:
            st.warning(f"No clear Landsat images found for {city_name} (2023-2026).")
            return None, None, None, None, None

        current_lst = landsat_col.median().select("ST_B10") \
            .multiply(0.00341802).add(149).subtract(273.15).multiply(1.8).add(32).clip(aoi)

        # 5. 2030 PREDICTION
        forecast_2030 = current_lst.add(trend.resample("bilinear").multiply(4)).rename("ST_B10")

        # 6. STATS EXTRACTION
        raw_stats = current_lst.reduceRegion(ee.Reducer.mean(), aoi, 30).getInfo()
        mean_val = raw_stats.get("ST_B10") if raw_stats else 0
        
        stats = {
            "city": city_name,
            "mean_temp_f": round(float(mean_val), 2) if mean_val else 0.0,
            "warming_trend": round(float(trend.reduceRegion(ee.Reducer.mean(), aoi, 1000).getInfo().get("slope", 0)), 4),
            "max_hotspot_f": round(float(current_lst.reduceRegion(ee.Reducer.max(), aoi, 30).getInfo().get("ST_B10", 0)), 2),
        }

        # 7. THUMBNAIL FOR GEMINI
        vis = {"min": 80, "max": 115, "palette": ["blue", "yellow", "red"], "dimensions": 512, "region": aoi}
        thumb_url = current_lst.getThumbURL(vis)

        return aoi, current_lst, forecast_2030, stats, thumb_url

    except Exception as e:
        st.error(f"Geospatial Logic Error: {e}")
        return None, None, None, None, None
