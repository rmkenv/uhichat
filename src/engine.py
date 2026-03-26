import ee
import streamlit as st
from google.oauth2 import service_account

def initialize_ee():
    """
    Initializes Earth Engine with automated PEM key cleaning.
    This fixes the 'InvalidByte(0, 92)' and 'Unable to load PEM' errors.
    """
    if not ee.data.is_initialized():
        try:
            # 1. Access the secrets from Streamlit
            if "gee_service_account" not in st.secrets:
                st.error("Secret 'gee_service_account' not found in Streamlit Secrets.")
                st.stop()
                
            sa_info = dict(st.secrets["gee_service_account"])
            
            # 2. KEY CLEANING: The Critical Fix
            # Converts the text string "\n" into actual functional line breaks
            if "private_key" in sa_info:
                # We replace a literal backslash + n with a real newline character
                cleaned_key = sa_info["private_key"].replace("\\n", "\n")
                sa_info["private_key"] = cleaned_key
            
            # 3. Create Credentials object
            credentials = service_account.Credentials.from_service_account_info(sa_info)
            
            # 4. Initialize the Earth Engine library
            ee.Initialize(
                credentials=credentials, 
                project=st.secrets["GCP_PROJECT_ID"]
            )
        except Exception as e:
            st.error(f"Failed to initialize Earth Engine: {e}")
            st.info("Check your Secrets formatting and ensure the Service Account has GEE access.")
            st.stop()

def get_gee_data(city_name):
    """
    Processes satellite data for the requested city.
    """
    # Always ensure we are initialized before running GEE commands
    initialize_ee()

    # 1. Geocode and Buffer the area
    try:
        aoi = ee.Algorithms.Geocoding.geometry(city_name).buffer(5000).bounds()
    except Exception:
        # Fallback if geocoding fails
        st.error(f"Could not find location: {city_name}")
        st.stop()
    
    # 2. MODIS 22-Year Trend (2003-2025)
    years = ee.List.sequence(2003, 2025)
    
    def modis_annual(y):
        date = ee.Date.fromYMD(y, 6, 1)
        img = ee.ImageCollection('MODIS/061/MYD11A2') \
            .filterBounds(aoi) \
            .filterDate(date, date.advance(4, 'month')) \
            .select('LST_Day_1km').mean()
        
        # Scale to Fahrenheit
        return img.multiply(0.02).subtract(273.15).multiply(1.8).add(32).set('year', y)

    modis_col = ee.ImageCollection(years.map(modis_annual))
    slope = modis_col.reduce(ee.Reducer.sensSlope()).select('slope')
    
    # 3. Landsat 8/9 30m Detail (Current Snapshot)
    landsat = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2") \
        .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")) \
        .filterBounds(aoi) \
        .filterDate('2024-01-01', '2025-12-31') \
        .filter(ee.Filter.lt('CLOUD_COVER', 20)) \
        .median()
    
    # Convert Thermal Band to Fahrenheit
    current_lst = landsat.select('ST_B10').multiply(0.00341802).add(149).subtract(273.15).multiply(1.8).add(32).clip(aoi)
    
    # 4. 2030 Forecast (Current + Slope * 5 years)
    forecast_2030 = current_lst.add(slope.resample('bilinear').multiply(5))
    
    # 5. Extract Stats for Gemini
    stats = {
        "mean_2025": current_lst.reduceRegion(ee.Reducer.mean(), aoi, 30).getInfo().get('ST_B10'),
        "warming_rate": slope.reduceRegion(ee.Reducer.mean(), aoi, 1000).getInfo().get('slope')
    }
    
    # 6. Generate URL for Gemini vision
    vis = {'min': 80, 'max': 115, 'palette': ['blue', 'yellow', 'red'], 'dimensions': 512, 'region': aoi}
    thumb_url = current_lst.getThumbURL(vis)
    
    return aoi, current_lst, forecast_2030, stats, thumb_url
