import ee
import streamlit as st
from google.oauth2 import service_account

def initialize_ee():
    """
    Initializes Earth Engine using the Service Account dictionary 
    stored in Streamlit Secrets.
    """
    if not ee.data.is_initialized():
        try:
            # Streamlit automatically parses the [gee_service_account] section 
            # from your secrets.toml into a Python dictionary.
            sa_info = st.secrets["gee_service_account"]
            
            # Create credentials from the service account info
            credentials = service_account.Credentials.from_service_account_info(sa_info)
            
            # Initialize the library with your specific project ID
            ee.Initialize(
                credentials=credentials,
                project=st.secrets["GCP_PROJECT_ID"]
            )
        except Exception as e:
            st.error(f"Failed to initialize Earth Engine: {e}")
            st.stop()

def get_gee_data(city_name):
    """
    Core Geospatial Engine: Processes 22 years of MODIS and 
    current Landsat 8/9 data for any city.
    """
    # 1. Ensure EE is initialized before running any code
    initialize_ee()

    # 2. Geocode and Buffer the Area of Interest (AOI)
    # We create a 5km square around the city center
    aoi = ee.Algorithms.Geocoding.geometry(city_name).buffer(5000).bounds()
    
    # 3. MODIS 22-Year Trend (Historical Engine)
    # We calculate the median summer LST for every year since 2003
    years = ee.List.sequence(2003, 2024)
    
    def modis_annual(y):
        date = ee.Date.fromYMD(y, 6, 1)
        img = ee.ImageCollection('MODIS/061/MYD11A2') \
            .filterBounds(aoi) \
            .filterDate(date, date.advance(4, 'month')) \
            .select('LST_Day_1km').mean()
        
        # Scale to Fahrenheit: (Scale * 0.02 - 273.15) * 1.8 + 32
        return img.multiply(0.02).subtract(273.15).multiply(1.8).add(32).set('year', y)

    modis_col = ee.ImageCollection(years.map(modis_annual))
    
    # Calculate Sen's Slope (The robust warming rate per year)
    slope = modis_col.reduce(ee.Reducer.sensSlope()).select('slope')
    
    # 4. Landsat 30m Baseline (Current Detail Engine)
    # Merging Landsat 8 and 9 for the highest resolution possible
    landsat = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2") \
        .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")) \
        .filterBounds(aoi) \
        .filterDate('2023-01-01', '2024-12-31') \
        .filter(ee.Filter.lt('CLOUD_COVER', 20)) \
        .median()
    
    # Convert Landsat Thermal Band 10 to Fahrenheit
    current_lst = landsat.select('ST_B10').multiply(0.00341802).add(149).subtract(273.15).multiply(1.8).add(32).clip(aoi)
    
    # 5. 2030 Forecast logic (Hybrid)
    # Predicted LST = Current + (Historical Warming Rate * 6 Years)
    forecast_2030 = current_lst.add(slope.resample('bilinear').multiply(6)).rename('PRED_2030')
    
    # 6. Statistical Extraction for Gemini
    # We reduce the images to single numbers for the AI to "read"
    stats = {
        "mean_2024": current_lst.reduceRegion(ee.Reducer.mean(), aoi, 30).getInfo().get('ST_B10'),
        "warming_rate": slope.reduceRegion(ee.Reducer.mean(), aoi, 1000).getInfo().get('slope'),
        "max_2024": current_lst.reduceRegion(ee.Reducer.max(), aoi, 30).getInfo().get('ST_B10')
    }
    
    # 7. Generate Image Thumbnail for Gemini's Vision
    # This allows the AI to see the spatial distribution of heat
    vis_params = {
        'min': 80, 
        'max': 115, 
        'palette': ['0000FF', 'FFFF00', 'FF0000'], # Blue to Yellow to Red
        'dimensions': 512, 
        'region': aoi
    }
    thumb_url = current_lst.getThumbURL(vis_params)
    
    return aoi, current_lst, forecast_2030, stats, thumb_url
