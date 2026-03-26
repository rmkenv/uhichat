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
        # Increase buffer slightly to 25km to ensure land pixel capture
        geometry = ee.Geometry.Point([lon, lat]).buffer(25000).bounds()

        # --- LAYER 1: MODIS 22-YEAR TREND ---
        years = ee.List.sequence(2003, 2024)
        def process_modis(y):
            y = ee.Number(y)
            # Expand window: May to October to ensure we get data
            start = ee.Date.fromYMD(y, 5, 1)
            img = ee.ImageCollection('MODIS/061/MYD11A2') \
                .filterBounds(geometry) \
                .filterDate(start, start.advance(5, 'month')) \
                .select('LST_Day_1km').median() # Median is more robust than mean
            
            lst_f = img.multiply(0.02).subtract(273.15).multiply(1.8).add(32)
            year_band = ee.Image.constant(y.subtract(2013)).rename('year').toFloat()
            # Check if image actually has pixels
            count = img.mask().reduceRegion(ee.Reducer.sum(), geometry, 1000).values().get(0)
            return lst_f.addBands(year_band).set('has_data', ee.Number(count).gt(0))

        modis_annual = ee.ImageCollection(years.map(process_modis)).filter(ee.Filter.eq('has_data', True))
        
        # SAFETY CHECK: Do we have at least 2 years for a regression?
        col_size = modis_annual.size().getInfo()
        
        if col_size >= 2:
            sen_reg = modis_annual.select(['year', 'LST_Day_1km']).reduce(ee.Reducer.robustLinearRegression(1, 1))
            sen_slope_f = sen_reg.select('coefficients').arrayProject([0]).arrayFlatten([['slope']])
        else:
            # Fallback to zero slope if data is missing
            sen_slope_f = ee.Image.constant(0).rename('slope')
            st.warning(f"Note: Limited historical MODIS data for {city_name}. Trend set to zero.")

        # --- LAYER 2: LANDSAT 30m BASELINE ---
        def get_ls(y):
            start = ee.Date.fromYMD(y, 6, 1)
            col = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")) \
                .filterBounds(geometry).filterDate(start, start.advance(4, 'month')).filter(ee.Filter.lt('CLOUD_COVER', 40))
            
            def mask(img):
                qa = img.select('QA_PIXEL')
                m = qa.bitwiseAnd(1 << 3).eq(0).And(qa.bitwiseAnd(1 << 4).eq(0))
                lst = img.select('ST_B10').multiply(0.00341802).add(149).subtract(273.15).multiply(1.8).add(32)
                return lst.updateMask(m).rename('LST_F')
            
            # If collection is empty, return a blank image with the right band name
            return ee.Image(ee.Algorithms.If(col.size().gt(0), col.map(mask).median(), ee.Image.constant(0).rename('LST_F')))

        landsat_stack = [ee.Image(get_ls(y)) for y in [2022, 2023, 2024]]
        avg_lst_f = ee.ImageCollection(landsat_stack).mean().rename('AVG_LST_F')
        
        # Forecast calculation
        pred_2026_f = avg_lst_f.add(sen_slope_f.resample('bilinear').multiply(4)).clip(geometry)

        # STATS Extraction with default values
        stats_dict = avg_lst_f.reduceRegion(ee.Reducer.mean(), geometry, 30).getInfo()
        slope_dict = sen_slope_f.reduceRegion(ee.Reducer.mean(), geometry, 1000).getInfo()

        mean_v = stats_dict.get('AVG_LST_F', 0) if stats_dict else 0
        slope_v = slope_dict.get('slope', 0) if slope_dict else 0

        stats = {
            "mean_temp_f": round(float(mean_v), 2),
            "warming_trend": round(float(slope_v), 4),
            "pred_2026_f": round(float(mean_v + (slope_v * 4)), 2)
        }
        
        vis = {"min": 85, "max": 115, "palette": ['blue', 'yellow', 'red'], "region": geometry, "dimensions": 512}
        return geometry, avg_lst_f, pred_2026_f, stats, pred_2026_f.getThumbURL(vis)
    
    except Exception as e:
        st.error(f"Critical Engine Error: {e}")
        return None, None, None, None, None
