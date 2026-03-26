import ee

def get_gee_data(city_name):
    # Geocode and Buffer
    aoi = ee.Algorithms.Geocoding.geometry(city_name).buffer(5000).bounds()
    
    # MODIS 22-Year Trend (Historical)
    years = ee.List.sequence(2003, 2024)
    def modis_annual(y):
        date = ee.Date.fromYMD(y, 6, 1)
        return ee.ImageCollection('MODIS/061/MYD11A2') \
            .filterBounds(aoi).filterDate(date, date.advance(4, 'month')) \
            .select('LST_Day_1km').mean() \
            .multiply(0.02).subtract(273.15).multiply(1.8).add(32).set('year', y)

    modis_col = ee.ImageCollection(years.map(modis_annual))
    slope = modis_col.reduce(ee.Reducer.sensSlope()).select('slope')
    
    # Landsat 30m Baseline (Current)
    landsat = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")) \
        .filterBounds(aoi).filterDate('2023-01-01', '2024-12-31').median()
    
    current_lst = landsat.select('ST_B10').multiply(0.00341802).add(149).subtract(273.15).multiply(1.8).add(32).clip(aoi)
    
    # 2030 Forecast (Slope * 6 years)
    forecast = current_lst.add(slope.resample('bilinear').multiply(6))
    
    # Extract Stats
    stats = {
        "mean_2024": current_lst.reduceRegion(ee.Reducer.mean(), aoi, 30).getInfo().get('ST_B10'),
        "warming_rate": slope.reduceRegion(ee.Reducer.mean(), aoi, 1000).getInfo().get('slope')
    }
    
    # Visual URL for Gemini
    vis = {'min': 80, 'max': 115, 'palette': ['blue', 'yellow', 'red'], 'dimensions': 512, 'region': aoi}
    thumb_url = current_lst.getThumbURL(vis)
    
    return aoi, current_lst, forecast, stats, thumb_url
