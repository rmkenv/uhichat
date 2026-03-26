import ee
import streamlit as st
import leafmap
from google.oauth2 import service_account

def clean_pem_key(key):
    if not key: return None
    key = key.replace("\\n", "\n").strip()
    header = "-----BEGIN PRIVATE KEY-----"
    footer = "-----END PRIVATE KEY-----"
    inner = key.replace(header, "").replace(footer, "").strip()
    return f"{header}\n{inner}\n{footer}\n"

def initialize_ee():
    if ee.data.is_initialized(): return 
    try:
        sa_info = dict(st.secrets["gee_service_account"])
        ee_scopes = ['https://www.googleapis.com/auth/earthengine']
        sa_info["private_key"] = clean_pem_key(sa_info["private_key"])
        credentials = service_account.Credentials.from_service_account_info(sa_info, scopes=ee_scopes)
        project_id = st.secrets.get("GCP_PROJECT_ID") or sa_info.get("project_id")
        ee.Initialize(credentials=credentials, project=project_id)
    except Exception as e:
        st.error(f"EE Auth Failed: {e}"); st.stop()

def get_gee_data(city_name: str, lon: float, lat: float):
    initialize_ee()
    try:
        # 1. Match GEE Script Geometry (10km buffer to ensure pixel overlap)
        geometry = ee.Geometry.Point([lon, lat]).buffer(10000).bounds()

        # 2. MODIS 22-Year Trend (Matching your GEE JS Logic)
        years = ee.List.sequence(2003, 2024)
        
        def process_modis(y):
            date = ee.Date.fromYMD(y, 6, 1)
            # Using MYD11A2 (Aqua) as per your script
            img = ee.ImageCollection('MODIS/061/MYD11A2') \
                .filterBounds(geometry) \
                .filterDate(date, date.advance(4, 'month')) \
                .select('LST_Day_1km').mean()
            
            # Match your JS Math: (K * 0.02 - 273.15) * 9/5 + 32
            # We add a check to see if the image has bands before doing math
            has_bands = img.bandNames().size().gt(0)
            
            return ee.Image(ee.Algorithms.If(
                has_bands,
                img.multiply(0.02).subtract(273.15).multiply(1.8).add(32) \
                   .set('year', y).set('system:time_start', date.millis()),
                ee.Image(0).set('year', y).set('has_data', False)
            ))

        modis_annual = ee.ImageCollection(years.map(process_modis)) \
            .filter(ee.Filter.listContains('system:band_names', 'LST_Day_1km'))

        if modis_annual.size().getInfo() < 2:
            st.error(f"MODIS found 0 bands for {city_name}. GEE Catalog may be lagging for this specific AOI.")
            return None, None, None, None, None

        sen_slope = modis_annual.select('LST_Day_1km').reduce(ee.Reducer.sensSlope()).select('slope')

        # 3. Landsat 5-Year Detail (Matching your JS Logic)
        def get_landsat(year):
            start = ee.Date.fromYMD(year, 6, 1)
            return ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
                .merge(ee.ImageCollection('LANDSAT/LC09/C02/T1_L2')) \
                .filterBounds(geometry) \
                .filterDate(start, start.advance(4, 'month')) \
                .filter(ee.Filter.lt('CLOUD_COVER', 30)) \
                .map(lambda img: img.select('ST_B10').multiply(0.00341802).add(149) \
                     .subtract(273.15).multiply(1.8).add(32) \
                     .updateMask(img.select('QA_PIXEL').bitwiseAnd(1 << 3).eq(0))) \
                .median()

        landsat_avg = ee.ImageCollection([ee.Image(get_landsat(y)) for y in [2020, 2021, 2022, 2023, 2024]]).mean()

        # 4. 2026 Forecast
        # landsatAvg + (slope * 4)
        pred_2026 = landsat_avg.add(sen_slope.resample('bilinear').multiply(4)).rename('PRED_2026').clip(geometry)

        # 5. Stats Extraction
        stats_raw = pred_2026.reduceRegion(reducer=ee.Reducer.mean(), geometry=geometry, scale=30).getInfo()
        
        # Trend stats for the agent
        trend_val = sen_slope.reduceRegion(reducer=ee.Reducer.mean(), geometry=geometry, scale=1000).getInfo()

        stats = {
            "city": city_name,
            "mean_temp_f": round(stats_raw.get('PRED_2026', 0), 2),
            "warming_trend": round(trend_val.get('slope', 0), 4),
            "max_hotspot_f": round(pred_2026.reduceRegion(ee.Reducer.max(), geometry, 30).getInfo().get('PRED_2026', 0), 2)
        }

        vis = {"min": 80, "max": 110, "palette": ['blue', 'yellow', 'red'], "dimensions": 512, "region": geometry}
        thumb_url = pred_2026.getThumbURL(vis)

        return geometry, landsat_avg, pred_2026, stats, thumb_url

    except Exception as e:
        st.error(f"Analysis Error: {e}")
        return None, None, None, None, None
