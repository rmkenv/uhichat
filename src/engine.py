import ee
import streamlit as st
import leafmap
from google.oauth2 import service_account

def clean_pem_key(key):
    """Standardizes PEM keys to prevent decryption errors."""
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
    Analyzes climate trends using Terra (Morning) satellite data to bypass 
    afternoon haze and coastal cloud masking.
    """
    initialize_ee()
    try:
        # 1. Define Area of Interest (Expanded to 15km for urban/coastal resilience)
        aoi = ee.Geometry.Point([lon, lat]).buffer(15000).bounds()

        # 2. Dynamic Date Detection using Terra (MOD11A2)
        # Terra has better morning clarity for coastal cities like NYC.
        latest_img = ee.ImageCollection("MODIS/061/MOD11A2") \
            .limit(1, "system:time_start", False).first()
        
        last_year = ee.Date(latest_img.get("system:time_start")).get("year").getInfo()
        start_year = last_year - 20 
        
        years = ee.List.sequence(start_year, last_year)
        
        def process_modis_year(y):
            # Window: April to September (captures the full thermal cycle)
            start = ee.Date.fromYMD(y, 4, 1)
            
            # Use Terra (MOD) instead of Aqua (MYD) for clearer morning pixels
            img = ee.ImageCollection("MODIS/061/MOD11A2") \
                .filterBounds(aoi) \
                .filterDate(start, start.advance(5, "month")) \
                .select("LST_Day_1km") \
                .median() 
            
            return img.set("year", y).set("has_data", img.bandNames().size().gt(0))

        # 3. Filter & Trend Calculation
        modis_col = ee.ImageCollection(years.map(process_modis_year)) \
            .filter(ee.Filter.eq("has_data", True))

        data_count = modis_col.size().getInfo()
        if data_count < 3:
            st.warning(f"⚠️ Only {data_count} years of clear data found for {city_name}. Trends cannot be calculated.")
            return None, None, None, None, None

        # Convert to Fahrenheit
        trend_images = modis_col.map(lambda img: 
            img.multiply(0.02).subtract(273.15).multiply(1.8).add(32))
        
        trend = trend_images.reduce(ee.Reducer.sensSlope()).select("slope")

        # 4. Current High-Res (Landsat 8/9)
        # Landsat also passes in the morning, making it compatible with Terra trends
        landsat_col = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2") \
            .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")) \
            .filterBounds(aoi) \
            .filterDate("2023-01-01", "2027-01-01") \
            .filter(ee.Filter.lt("CLOUD_COVER", 50)) 

        if landsat_col.size().getInfo() == 0:
            st.warning(f"No clear Landsat images found for {city_name} (2023-2026).")
            return None, None, None, None, None

        current_lst = landsat_col.median().select("ST_B10") \
            .multiply(0.00341802).add(149).subtract(273.15).multiply(1.8).add(32).clip(aoi)

        # 5. 2030 Prediction
        forecast_2030 = current_lst.add(trend.resample("bilinear").multiply(4)).rename("ST_B10")

        # 6. Stats Extraction
        raw_stats = current_lst.reduceRegion(ee.Reducer.mean(), aoi, 30).getInfo()
        mean_val = raw_stats.get("ST_B10") if raw_stats else 0
        
        stats = {
            "city": city_name,
            "mean_temp_f": round(float(mean_val), 2) if mean_val else 0.0,
            "warming_trend": round(float(trend.reduceRegion(ee.Reducer.mean(), aoi, 1000).getInfo().get("slope", 0)), 4),
            "max_hotspot_f": round(float(current_lst.reduceRegion(ee.Reducer.max(), aoi, 30).getInfo().get("ST_B10", 0)), 2),
        }

        # 7. Thumbnail
        vis = {"min": 80, "max": 115, "palette": ["blue", "yellow", "red"], "dimensions": 512, "region": aoi}
        thumb_url = current_lst.getThumbURL(vis)

        return aoi, current_lst, forecast_2030, stats, thumb_url

    except Exception as e:
        st.error(f"Geospatial Logic Error: {e}")
        return None, None, None, None, None
