import ee
import streamlit as st
import leafmap
from google.oauth2 import service_account

def clean_pem_key(key):
    """Fixes 'InvalidByte' errors by cleaning and rebuilding the PEM key."""
    if not key: return None
    key = key.replace("\\n", "\n").strip()
    header = "-----BEGIN PRIVATE KEY-----"
    footer = "-----END PRIVATE KEY-----"
    inner = key.replace(header, "").replace(footer, "").strip()
    return f"{header}\n{inner}\n{footer}\n"

def initialize_ee():
    """Initializes EE with explicit scopes to fix 'invalid_scope' errors."""
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
    """Analyzes climate trends while strictly preventing 'No Bands' math errors."""
    initialize_ee()
    try:
        # 1. Define AOI (5km buffer)
        aoi = ee.Geometry.Point([lon, lat]).buffer(5000).bounds()

        # 2. Historical Trend (MODIS 2003–2026)
        # We must filter out years with zero data before calculating the slope
        years = ee.List.sequence(2003, 2026)
        
        def process_modis_year(y):
            start = ee.Date.fromYMD(y, 6, 1)
            img = ee.ImageCollection("MODIS/061/MYD11A2") \
                .filterBounds(aoi) \
                .filterDate(start, start.advance(3, "month")) \
                .select("LST_Day_1km").mean()
            
            # Metadata tag: does this year actually have a band to multiply?
            return img.set("year", y).set("has_data", img.bandNames().size().gt(0))

        # Filter the collection to REMOVE empty years before reducing
        modis_col = ee.ImageCollection(years.map(process_modis_year)) \
            .filter(ee.Filter.eq("has_data", True))

        # Logic Guard: Need at least 2 points to draw a trend line
        if modis_col.size().getInfo() < 2:
            st.warning(f"Insufficient historical data for {city_name} to calculate trends.")
            return None, None, None, None, None

        # Convert MODIS to Fahrenheit ONLY for valid images
        trend_images = modis_col.map(lambda img: 
            img.multiply(0.02).subtract(273.15).multiply(1.8).add(32))
        
        # Calculate Sens Slope (warming trend)
        trend = trend_images.reduce(ee.Reducer.sensSlope()).select("slope")

        # 3. Current High-Res (Landsat 8/9, 30m)
        landsat_col = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2") \
            .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")) \
            .filterBounds(aoi) \
            .filterDate("2023-01-01", "2026-12-31") \
            .filter(ee.Filter.lt("CLOUD_COVER", 45)) # High tolerance for hazy regions

        # FIX: The 'Got 0 and 1' error guard
        if landsat_col.size().getInfo() == 0:
            st.warning(f"No clear Landsat images found for {city_name} (2023-2026).")
            return None, None, None, None, None

        # Process the median image safely
        current_lst = landsat_col.median().select("ST_B10") \
            .multiply(0.00341802).add(149).subtract(273.15).multiply(1.8).add(32).clip(aoi)

        # 4. 2030 Prediction (Trend extrapolated 4 years from now)
        forecast_2030 = current_lst.add(trend.resample("bilinear").multiply(4)).rename("ST_B10")

        # 5. Extract Stats with 'None' safety
        # We fetch the dictionary and provide defaults if a region is unmasked
        raw_stats = current_lst.reduceRegion(ee.Reducer.mean(), aoi, 30).getInfo()
        mean_val = raw_stats.get("ST_B10") if raw_stats else 0
        
        stats = {
            "city": city_name,
            "mean_temp_f": round(float(mean_val), 2) if mean_val else 0.0,
            "warming_trend": round(float(trend.reduceRegion(ee.Reducer.mean(), aoi, 1000).getInfo().get("slope", 0)), 4),
            "max_hotspot_f": round(float(current_lst.reduceRegion(ee.Reducer.max(), aoi, 30).getInfo().get("ST_B10", 0)), 2),
        }

        # 6. Generate Thumbnail for Gemini Vision
        vis = {"min": 80, "max": 115, "palette": ["blue", "yellow", "red"], "dimensions": 512, "region": aoi}
        thumb_url = current_lst.getThumbURL(vis)

        return aoi, current_lst, forecast_2030, stats, thumb_url

    except Exception as e:
        st.error(f"Geospatial Analysis Error: {e}")
        return None, None, None, None, None
