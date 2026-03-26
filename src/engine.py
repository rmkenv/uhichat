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
        # 1. GEOMETRY: 25km for high-res stats, 50km for regional trend stability
        point = ee.Geometry.Point([lon, lat])
        geometry = point.buffer(25000).bounds()
        regional_geo = point.buffer(50000).bounds()

        # ═════════════════════════════════════════════════════════════
        # LAYER 1 — MODIS 22-YEAR TREND (1km Scale)
        # ═════════════════════════════════════════════════════════════
        years = ee.List.sequence(2003, 2025)
        
        def process_modis(y):
            y = ee.Number(y)
            start = ee.Date.fromYMD(y, 6, 1)
            # Filter for Summer (June - Sept)
            col = ee.ImageCollection('MODIS/061/MYD11A2') \
                .filterBounds(regional_geo) \
                .filterDate(start, start.advance(4, 'month')) \
                .select('LST_Day_1km')
            
            # Using Mean to fill gaps in coastal pixels
            img = col.mean()
            
            # Formula: (K * 0.02 - 273.15) * 1.8 + 32
            lst_f = img.multiply(0.02).subtract(273.15).multiply(1.8).add(32)
            year_band = ee.Image.constant(y.subtract(2013)).rename('year').toFloat()
            
            # Validity Check: Does the image have actual data pixels?
            has_data = img.mask().reduceRegion(
                reducer=ee.Reducer.anyNonZero(),
                geometry=regional_geo,
                scale=1000
            ).values().contains(1)
            
            return lst_f.addBands(year_band).set('has_data', has_data)

        modis_annual = ee.ImageCollection(years.map(process_modis)) \
            .filter(ee.Filter.eq('has_data', True))

        # Robust Regression for the Slope (Fahrenheit change per year)
        col_size = modis_annual.size().getInfo()
        if col_size > 5:
            sen_reg = modis_annual.select(['year', 'LST_Day_1km']) \
                .reduce(ee.Reducer.robustLinearRegression(1, 1))
            sen_slope_f = sen_reg.select('coefficients') \
                .arrayProject([0]).arrayFlatten([['slope']])
        else:
            sen_slope_f = ee.Image.constant(0.05).rename('slope') # Default global avg fallback

        # ═════════════════════════════════════════════════════════════
        # LAYER 2 — LANDSAT 30m BASELINE (Neighborhood Scale)
        # ═════════════════════════════════════════════════════════════
        def get_landsat_composite(y_list):
            col = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2") \
                .merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")) \
                .filterBounds(geometry) \
                .filter(ee.Filter.calendarRange(6, 9, 'month')) \
                .filter(ee.Filter.inList('year', y_list)) \
                .filter(ee.Filter.lt('CLOUD_COVER', 40))
            
            def prep_landsat(img):
                qa = img.select('QA_PIXEL')
                # Earth Engine .And() is required here
                mask = qa.bitwiseAnd(1 << 3).eq(0).And(qa.bitwiseAnd(1 << 4).eq(0))
                lst = img.select('ST_B10').multiply(0.00341802).add(149)\
                         .subtract(273.15).multiply(1.8).add(32)
                return lst.updateMask(mask).rename('LST_F')

            return col.map(prep_landsat).median()

        # Create a 3-year median baseline (2022-2024)
        avg_lst_f = get_landsat_composite([2022, 2023, 2024]).rename('AVG_LST_F')

        # ═════════════════════════════════════════════════════════════
        # PREDICTION & STATISTICS
        # ═════════════════════════════════════════════════════════════
        # 2026 Forecast = Baseline + (Slope * 2 Years since 2024)
        pred_2026_f = avg_lst_f.add(sen_slope_f.resample('bilinear').multiply(2)).clip(geometry)

        # Extract numerical results for Streamlit Metrics
        stats_raw = avg_lst_f.reduceRegion(ee.Reducer.mean(), geometry, 30).getInfo()
        slope_raw = sen_slope_f.reduceRegion(ee.Reducer.mean(), geometry, 1000).getInfo()

        # Handle potential None values from GEE
        mean_val = stats_raw.get('AVG_LST_F', 0) if stats_raw else 0
        slope_val = slope_raw.get('slope', 0) if slope_raw else 0

        stats = {
            "mean_temp_f": round(float(mean_val), 2),
            "warming_trend": round(float(slope_val), 4),
            "pred_2026_f": round(float(mean_val + (slope_val * 2)), 2)
        }
        
        # Visual parameters for the thumbnail
        vis_params = {
            "min": 85, "max": 115, 
            "palette": ['blue', 'yellow', 'red'], 
            "region": geometry, 
            "dimensions": 512
        }
        
        return geometry, avg_lst_f, pred_2026_f, stats, pred_2026_f.getThumbURL(vis_params)

    except Exception as e:
        st.error(f"Engine Core Error: {e}")
        return None, None, None, None, None
