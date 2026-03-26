import ee
import streamlit as st
import leafmap
from google.oauth2 import service_account

def clean_pem_key(key):
    """
    Rips out common copy-paste artifacts that cause 'InvalidByte' errors.
    Standardizes the key for the cryptography library.
    """
    if not key:
        return None
    
    # 1. Fix literal '\n' text strings often found in JSON/TOML pastes
    key = key.replace("\\n", "\n")
    
    # 2. Remove accidental whitespace or invisible characters
    key = key.strip()
    
    # 3. Standardize Headers/Footers
    # This prevents 'InvalidByte' errors caused by missing dashes or extra spaces
    header = "-----BEGIN PRIVATE KEY-----"
    footer = "-----END PRIVATE KEY-----"
    
    # Strip everything to get the raw Base64, then rebuild perfectly
    inner_content = key.replace(header, "").replace(footer, "").strip()
    return f"{header}\n{inner_content}\n{footer}\n"

def initialize_ee():
    """
    Initializes Earth Engine with robust error handling for Streamlit.
    """
    # Check if already initialized to save API overhead
    try:
        ee.data.get_info()
        return 
    except Exception:
        pass

    try:
        if "gee_service_account" not in st.secrets:
            st.error("Missing 'gee_service_account' in Streamlit Secrets!")
            st.stop()
        
        # Convert Secret object to dict to allow modification
        sa_info = dict(st.secrets["gee_service_account"])
        
        # Apply the cleaning logic to the private key
        sa_info["private_key"] = clean_pem_key(sa_info["private_key"])
        
        # Create credentials
        credentials = service_account.Credentials.from_service_account_info(sa_info)
        
        # Initialize with Project ID from secrets
        project_id = st.secrets.get("GCP_PROJECT_ID") or sa_info.get("project_id")
        ee.Initialize(credentials=credentials, project=project_id)
        
    except Exception as e:
        # If this still fails, the key itself is likely truncated/incomplete
        st.error(f"Failed to initialize Earth Engine: {e}")
        st.info("💡 Hint: Ensure you copied the FULL 'private_key' string from your JSON file.")
        st.stop()

def get_gee_data(city_name: str, lon: float, lat: float):
    """
    Processes 20-year climate trends and 30m thermal data using coordinates.
    """
    initialize_ee()

    try:
        # 1. Define Area of Interest (5km buffer around point)
        aoi = ee.Geometry.Point([lon, lat]).buffer(5000).bounds()

        # 2. Historical Trend (MODIS 2003–2026)
        years = ee.List.sequence(2003, 2026)
        
        def calculate_annual_temp(y):
            start = ee.Date.fromYMD(y, 6, 1)
            return ee.ImageCollection("MODIS/061/MYD11A2") \
                .filterBounds(aoi) \
                .filterDate(start, start.advance(3, "month")) \
                .select("LST_Day_1km").mean() \
                .multiply(0.02).subtract(273.15).multiply(1.8).add(32) \
                .set("year", y)

        modis_col = ee.ImageCollection(years.map(calculate_annual_temp))
        trend = modis_col.reduce(ee.Reducer.sensSlope()).select("slope")

        # 3. Current High-Res Baseline (Landsat 8/9, 30m)
        current_lst = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2") \
            .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")) \
            .filterBounds(aoi) \
            .filterDate("2024-01-01", "2027-01-01") \
            .filter(ee.Filter.lt("CLOUD_COVER", 15)) \
            .median() \
            .select("ST_B10").multiply(0.00341802).add(149).subtract(273.15).multiply(1.8).add(32) \
            .clip(aoi)

        # 4. 2030 Prediction (Current + Trend * 4 years)
        forecast_2030 = current_lst.add(trend.resample("bilinear").multiply(4)).rename("ST_B10")

        # 5. Extract Stats for Gemini Reasoning
        stats = {
            "city": city_name,
            "mean_temp_f": current_lst.reduceRegion(ee.Reducer.mean(), aoi, 30).getInfo().get("ST_B10"),
            "warming_trend_f_per_year": trend.reduceRegion(ee.Reducer.mean(), aoi, 1000).getInfo().get("slope"),
            "max_hotspot_f": current_lst.reduceRegion(ee.Reducer.max(), aoi, 30).getInfo().get("ST_B10"),
        }

        # 6. Generate static thumbnail for Gemini Vision (Text-to-Image context)
        vis = {"min": 80, "max": 115, "palette": ["blue", "yellow", "red"], "dimensions": 512, "region": aoi}
        thumb_url = current_lst.getThumbURL(vis)

        return aoi, current_lst, forecast_2030, stats, thumb_url

    except Exception as e:
        st.error(f"Geospatial Processing Error: {e}")
        return None, None, None, None, None
