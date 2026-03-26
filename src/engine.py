import ee
import streamlit as st
from google.oauth2 import service_account

def clean_pem_key(key):
    if not key: return None
    key = key.replace("\\n", "\n").strip()
    header, footer = "-----BEGIN PRIVATE KEY-----", "-----END PRIVATE KEY-----"
    inner = key.replace(header, "").replace(footer, "").strip()
    return f"{header}\n{inner}\n{footer}\n"

def initialize_ee():
    if ee.data.is_initialized(): return 
    try:
        sa_info = dict(st.secrets["gee_service_account"])
        sa_info["private_key"] = clean_pem_key(sa_info["private_key"])
        credentials = service_account.Credentials.from_service_account_info(
            sa_info, scopes=['https://www.googleapis.com/auth/earthengine']
        )
        ee.Initialize(credentials=credentials, project=st.secrets.get("GCP_PROJECT_ID") or sa_info.get("project_id"))
    except Exception as e:
        st.error(f"EE Auth Failed: {e}"); st.stop()

def get_gee_data(city_name: str, lon: float, lat: float):
    initialize_ee()
    try:
        # 1. Expand Geometry to 20km to guarantee pixel capture
        geometry = ee.Geometry.Point([lon, lat]).buffer(20000).bounds()

        # 2. MODIS Collection with strict "Has Data" check
        years = ee.List.sequence(2003, 2025)
        
        def process_modis(y):
            date = ee.Date.fromYMD(y, 5, 1) # Start earlier (May) to catch more clear days
            img = ee.ImageCollection('MODIS/061/MYD11A2') \
                .filterBounds(geometry) \
                .filterDate(date, date.advance(5, 'month')) \
                .select('LST_Day_1km').median() # Median is more robust than mean
            
            # Map math and set a flag if the image is valid
            return img.multiply(0.02).subtract(273.15).multiply(1.8).add(32) \
                .set('year', y) \
                .set('system:time_start', date.millis()) \
                .set('band_count', img.bandNames().size())

        # Filter the collection BEFORE reducing
        modis_col = ee.ImageCollection(years.map(process_modis)) \
            .filter(ee.Filter.gt('band_count', 0))

        # Check collection size on the server
        count = modis_col.size().getInfo()
        
        if count < 2:
            st.warning(f"⚠️ Insufficient historical data (found {count} years) for {city_name}. Trend calculation skipped.")
            sen_slope = ee.Image(0).rename('slope') # Dummy slope
        else:
            sen_slope = modis_col.reduce(ee.Reducer.sensSlope()).select('slope')

        # 3. Landsat 5-Year High-Res (2020-2026)
        landsat_col = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
            .merge(ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')) \
            .filterBounds(geometry) \
            .filterDate('2022-01-01', '2026-12-31') \
            .filter(ee.Filter.lt('CLOUD_COVER', 40))

        if landsat_col.size().getInfo() == 0:
            st.error("No Landsat imagery available for this region.")
            return None, None, None, None, None

        current_lst = landsat_col.median().select('ST_B10') \
            .multiply(0.00341802).add(149).subtract(273.15).multiply(1.8).add(32).clip(geometry)

        # 4. Forecast 2030 (Slope * 4 years)
        forecast_2030 = current_lst.add(sen_slope.resample('bilinear').multiply(4)).rename('ST_B10')

        # 5. Stats Extraction
        mean_f = current_lst.reduceRegion(ee.Reducer.mean(), geometry, 30).getInfo().get('ST_B10', 0)
        slope_f = sen_slope.reduceRegion(ee.Reducer.mean(), geometry, 1000).getInfo().get('slope', 0)

        stats = {
            "city": city_name,
            "mean_temp_f": round(float(mean_f), 2),
            "warming_trend": round(float(slope_f), 4),
            "max_hotspot_f": round(float(current_lst.reduceRegion(ee.Reducer.max(), geometry, 30).getInfo().get('ST_B10', 0)), 2)
        }

        vis = {"min": 80, "max": 110, "palette": ['blue', 'yellow', 'red'], "dimensions": 512, "region": geometry}
        thumb_url = current_lst.getThumbURL(vis)

        return geometry, current_lst, forecast_2030, stats, thumb_url

    except Exception as e:
        st.error(f"Python-side Analysis Error: {e}")
        return None, None, None, None, None
