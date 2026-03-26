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
        project_id = st.secrets.get("GCP_PROJECT_ID") or sa_info.get("project_id")
        ee.Initialize(credentials=credentials, project=project_id)
    except Exception as e:
        st.error(f"EE Auth Failed: {e}"); st.stop()

def get_gee_data(city_name: str, lon: float, lat: float):
    initialize_ee()
    try:
        # 1. STUDY AREA (20km buffer for statistical grounding)
        geometry = ee.Geometry.Point([lon, lat]).buffer(20000).bounds()

        # --- LAYER 1: MODIS 22-YEAR TREND ---
        years = ee.List.sequence(2003, 2024)
        
        def process_modis(y):
            y = ee.Number(y)
            start = ee.Date.fromYMD(y, 6, 1)
            img = ee.ImageCollection('MODIS/061/MYD11A2') \
                .filterBounds(geometry) \
                .filterDate(start, start.advance(4, 'month')) \
                .select('LST_Day_1km').mean()
            
            # Math: (K * 0.02 - 273.15) * 1.8 + 32
            lst_f = img.multiply(0.02).subtract(273.15).multiply(1.8).add(32)
            year_band = ee.Image.constant(y.subtract(2013)).rename('year').toFloat()
            
            return lst_f.addBands(year_band) \
                .set('year', y) \
                .set('has_data', img.bandNames().size().gt(0))

        modis_annual = ee.ImageCollection(years.map(process_modis)) \
            .filter(ee.Filter.eq('has_data', True))

        # Robust Linear Regression (Sen's Slope Proxy)
        sen_reg = modis_annual.select(['year', 'LST_Day_1km']) \
            .reduce(ee.Reducer.robustLinearRegression(numX=1, numY=1))
        
        sen_slope_f = sen_reg.select('coefficients') \
            .arrayProject([0]).arrayFlatten([['sens_slope_F']])

        # --- LAYER 2: LANDSAT 30m BASELINE ---
        def get_landsat_summer(y):
            start = ee.Date.fromYMD(y, 6, 1)
            col = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2") \
                .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")) \
                .filterBounds(geometry) \
                .filterDate(start, start.advance(4, 'month')) \
                .filter(ee.Filter.lt('CLOUD_COVER', 30))
            
            def prep_landsat(img):
                qa = img.select('QA_PIXEL')
                # Corrected Syntax: Using .And() instead of python 'and'
                mask = qa.bitwiseAnd(1 << 3).eq(0).And(qa.bitwiseAnd(1 << 4).eq(0))
                lst = img.select('ST_B10').multiply(0.00341802).add(149).subtract(273.15).multiply(1.8).add(32)
                return lst.updateMask(mask).rename('LST_F')

            return col.map(prep_landsat).median()

        landsat_annual = ee.ImageCollection([
            ee.Image(get_landsat_summer(y)) for y in [2021, 2022, 2023, 2024]
        ])

        avg_lst_f = landsat_annual.mean().rename('AVG_LST_F')

        # --- PREDICTION & SUHI ---
        # 2026 Forecast: Baseline + (Slope * 4 years)
        pred_2026_f = avg_lst_f.add(sen_slope_f.resample('bilinear').multiply(4)).clip(geometry)

        # Urban Heat Intensity (Simple Rural Ref)
        stats_raw = avg_lst_f.reduceRegion(ee.Reducer.mean(), geometry, 30).getInfo()
        slope_raw = sen_slope_f.reduceRegion(ee.Reducer.mean(), geometry, 1000).getInfo()

        stats = {
            "city": city_name,
            "mean_temp_f": round(float(stats_raw.get('AVG_LST_F', 0)), 2),
            "warming_trend": round(float(slope_raw.get('sens_slope_F', 0)), 4),
            "pred_2026_f": round(float(stats_raw.get('AVG_LST_F', 0) + (slope_raw.get('sens_slope_F', 0) * 4)), 2)
        }

        vis = {"min": 85, "max": 115, "palette": ['blue', 'yellow', 'red'], "region": geometry, "dimensions": 512}
        thumb_url = pred_2026_f.getThumbURL(vis)

        return geometry, avg_lst_f, pred_2026_f, stats, thumb_url

    except Exception as e:
        st.error(f"Engine Error: {e}")
        return None, None, None, None, None
