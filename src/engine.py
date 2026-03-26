import ee
import streamlit as st
import leafmap
from google.oauth2 import service_account

def clean_pem_key(key):
    """
    Standardizes the PEM key to prevent 'InvalidByte' errors during decryption.
    """
    if not key:
        return None
    
    # 1. Fix literal '\n' text strings often found in JSON/TOML pastes
    key = key.replace("\\n", "\n").strip()
    
    header = "-----BEGIN PRIVATE KEY-----"
    footer = "-----END PRIVATE KEY-----"
    
    # 2. Rebuild the key perfectly to ensure no missing/extra characters at boundaries
    inner_content = key.replace(header, "").replace(footer, "").strip()
    return f"{header}\n{inner_content}\n{footer}\n"

def initialize_ee():
    """
    Initializes Earth Engine with explicit scopes and robust secret handling.
    """
    # Skip if already initialized (improves performance)
    if ee.data.is_initialized():
        return 

    try:
        if "gee_service_account" not in st.secrets:
            st.error("Missing 'gee_service_account' in Streamlit Secrets!")
            st.stop()
        
        sa_info = dict(st.secrets["gee_service_account"])
        
        # FIX: 'invalid_scope' error by explicitly requesting EE access
        ee_scopes = ['https://www.googleapis.com/auth/earthengine']
        
        # FIX: 'InvalidByte' error by cleaning the key
        sa_info["private_key"] = clean_pem_key(sa_info["private_key"])
        
        # Create credentials with explicit scopes
        credentials = service_account.Credentials.from_service_account_info(
            sa_info, 
            scopes=ee_scopes
        )
        
        # Initialize with Project ID from secrets or service account
        project_id = st.secrets.get("GCP_PROJECT_ID") or sa_info.get("project_id")
        ee.Initialize(credentials=credentials, project=project_id)
        
    except Exception as e:
        st.error(f"Failed to initialize Earth Engine: {e}")
        st.stop()

def get_gee_data(city_name: str, lon: float, lat: float):
    """
    Performs geospatial analysis for current and future thermal trends.
    """
    initialize_ee()

    try:
        # 1. Define Area of Interest (5km radius buffer)
        aoi = ee.Geometry.Point([lon, lat]).buffer(5000).bounds()

        # 2. Historical Trend (MODIS LST 1km, 2003–2026)
        # We use MODIS for the trend because it has a consistent 20+ year daily record
        years = ee.List.sequence(2003, 2026)
        
        def calculate_annual_temp(y):
            start = ee.Date.fromYMD(y, 6, 1) # Target Summer (June-Aug)
            return ee.ImageCollection("MODIS/061/MYD11A2") \
                .filterBounds(aoi) \
                .filterDate(start, start.advance(3, "month")) \
                .select("LST_Day_1km").mean() \
                .multiply(0.02).subtract(273.15).multiply(1.8).add(32) \
                .set("year", y)

        modis_col = ee.ImageCollection(years.map(calculate_annual_temp))
        trend = modis_col.reduce(ee.Reducer.sensSlope()).select("slope")

        # 3. Current High-Res Baseline (Landsat 8/9, 30m)
        landsat_col = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2") \
            .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")) \
            .filterBounds(aoi) \
            .filterDate("2023-01-01", "2026-12-31") \
            .filter(ee.Filter.lt("CLOUD_COVER", 35)) # Loosened for data availability

        # FIX: 'Image.multiply' 0 bands error by checking if collection is empty
        if landsat_col.size().getInfo() == 0:
            st.warning(f"⚠️ No clear satellite imagery found for {city_name} in current window.")
            return None, None, None, None, None

        current_lst = landsat_col.median() \
            .select("ST_B10").multiply(0.00341802).add(149).subtract(273.15).multiply(1.8).add(32) \
            .clip(aoi)

        # 4. 2030 Prediction (Current + (Trend * 4 Years))
        forecast_2030 = current_lst.add(trend.resample("bilinear").multiply(4)).rename("ST_B10")

        # 5. Extract Stats for Gemini Analysis
        # Note: resample trend to match Landsat 30m resolution for processing
        stats = {
            "city": city_name,
            "mean_temp_f": round(float(current_lst.reduceRegion(ee.Reducer.mean(), aoi, 30).getInfo().get("ST_B10")), 2),
            "warming_trend": round(float(trend.reduceRegion(ee.Reducer.mean(), aoi, 1000).getInfo().get("slope")), 4),
            "max_hotspot_f": round(float(current_lst.reduceRegion(ee.Reducer.max(), aoi, 30).getInfo().get("ST_B10")), 2),
        }

        # 6. Generate thumbnail for Gemini Vision context
        vis = {"min": 80, "max": 115, "palette": ["blue", "yellow", "red"], "dimensions": 512, "region": aoi}
        thumb_url = current_lst.getThumbURL(vis)

        return aoi, current_lst, forecast_2030, stats, thumb_url

    except Exception as e:
        st.error(f"Geospatial Analysis Error: {e}")
        return None, None, None, None, None
