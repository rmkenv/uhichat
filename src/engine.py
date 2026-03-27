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
        point = ee.Geometry.Point([lon, lat])
        geometry = point.buffer(20000).bounds()
        regional_geo = point.buffer(50000).bounds()

        # --- 1. MODIS 22-YEAR TREND ---
        years = ee.List.sequence(2003, 2025)
        def process_modis(y):
            y = ee.Number(y)
            img = ee.ImageCollection('MODIS/061/MYD11A2') \
                .filterBounds(regional_geo) \
                .filterDate(ee.Date.fromYMD(y, 6, 1), ee.Date.fromYMD(y, 9, 30)) \
                .select('LST_Day_1km').mean()
            lst_f = img.multiply(0.02).subtract(273.15).multiply(1.8).add(32)
            year_band = ee.Image.constant(y.subtract(2013)).rename('year').toFloat()
            return lst_f.addBands(year_band).set('has_data', img.bandNames().size().gt(0))

        modis_annual = ee.ImageCollection(years.map(process_modis)).filter(ee.Filter.eq('has_data', True))
        
        if modis_annual.size().getInfo() > 5:
            sen_reg = modis_annual.select(['year', 'LST_Day_1km']).reduce(ee.Reducer.robustLinearRegression(1, 1))
            sen_slope_f = sen_reg.select('coefficients').arrayProject([0]).arrayFlatten([['slope']])
        else:
            sen_slope_f = ee.Image.constant(0.05).rename('slope')

        # --- 2. LANDSAT 30m BASELINE ---
        ls_col = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")) \
            .filterBounds(geometry).filter(ee.Filter.calendarRange(2020, 2025, 'year')) \
            .filter(ee.Filter.calendarRange(6, 9, 'month')).filter(ee.Filter.lt('CLOUD_COVER', 50))
            
        def prep_ls(img):
            qa = img.select('QA_PIXEL')
            mask = qa.bitwiseAnd(1 << 3).eq(0).And(qa.bitwiseAnd(1 << 4).eq(0))
            lst = img.select('ST_B10').multiply(0.00341802).add(149).subtract(273.15).multiply(1.8).add(32)
            return lst.updateMask(mask).rename('AVG_LST_F')

        avg_lst_f = ls_col.map(prep_ls).median()
        if avg_lst_f.bandNames().size().getInfo() == 0:
            avg_lst_f = modis_annual.select('LST_Day_1km').mean().rename('AVG_LST_F').clip(geometry)

        # --- 3. FORECAST & VIS ---
        slope_resampled = sen_slope_f.resample('bilinear').reproject(crs='EPSG:4326', scale=30)
        pred_2026_f = avg_lst_f.add(slope_resampled.multiply(2)).clip(geometry)

        stats_raw = avg_lst_f.reduceRegion(ee.Reducer.mean(), geometry, 30).getInfo()
        slope_raw = sen_slope_f.reduceRegion(ee.Reducer.mean(), regional_geo, 1000).getInfo()

        vis_params = {"min": 80, "max": 120, "palette": ['#0000ff', '#ffff00', '#ff0000']}

        stats = {
            "mean_temp_f": round(float(stats_raw.get('AVG_LST_F', 0) if stats_raw else 0), 2),
            "warming_trend": round(float(slope_raw.get('slope', 0) if slope_raw else 0), 4),
            "pred_2026_f": round(float((stats_raw.get('AVG_LST_F', 0) if stats_raw else 0) + 
                                       ((slope_raw.get('slope', 0) if slope_raw else 0) * 2)), 2),
            "vis_min": vis_params["min"],
            "vis_max": vis_params["max"],
            "palette": vis_params["palette"]
        }
        
        return geometry, avg_lst_f, pred_2026_f, stats

    except Exception as e:
        st.error(f"Engine Core Error: {e}")
        return None, None, None, None
