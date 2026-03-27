import streamlit as st
import leafmap.foliumap as leafmap
import sys
import os

# 1. PATH FIX: Ensures the app can see the 'src' folder
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.engine import get_gee_data

# 2. PAGE CONFIG
st.set_page_config(page_title="Urban Heat Agent 2026", layout="wide", page_icon="🔥")

# 3. HIGH-CONTRAST CSS: Fixes white-on-white text issues
st.markdown("""
    <style>
    .main { background-color: #f8fafc; }
    [data-testid="stMetric"] {
        background-color: #ffffff !important;
        padding: 20px !important;
        border-radius: 12px !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
    }
    [data-testid="stMetricLabel"] { color: #475569 !important; font-weight: 600 !important; }
    [data-testid="stMetricValue"] { color: #1e293b !important; font-weight: 800 !important; }
    </style>
    """, unsafe_allow_html=True)

# 4. SIDEBAR
st.sidebar.title("🏙️ Heat Agent v2.2")
CITIES = {
    "Atlanta, GA": {"lat": 33.7490, "lon": -84.3880},
    "New York, NY": {"lat": 40.7128, "lon": -74.0060},
    "Phoenix, AZ": {"lat": 33.4484, "lon": -112.0740},
    "Chicago, IL": {"lat": 41.8781, "lon": -87.6298},
    "Los Angeles, CA": {"lat": 34.0522, "lon": -118.2437}
}

selected_city = st.sidebar.selectbox("Select Target City", list(CITIES.keys()))
coords = CITIES[selected_city]

# 5. DATA FETCHING
with st.spinner(f"Requesting satellite tiles for {selected_city}..."):
    geom, current_lst, forecast_2026, stats = get_gee_data(
        selected_city, coords["lon"], coords["lat"]
    )

# 6. DASHBOARD MAIN UI
if stats:
    st.title(f"Thermal Analysis: {selected_city}")
    
    # METRICS ROW
    m1, m2, m3 = st.columns(3)
    m1.metric("Baseline Surface Temp", f"{stats['mean_temp_f']}°F")
    m2.metric("22-Year Warming Trend", f"{stats['warming_trend']}°F/yr")
    
    gain = round(stats['pred_2026_f'] - stats['mean_temp_f'], 2)
    m3.metric("2026 Forecast", f"{stats['pred_2026_f']}°F", delta=f"{gain}°F Gain")

    st.markdown("---")

    # 7. THE MAP (The Fix for the Missing Layer)
    st.subheader("Interactive Heat Mapping (30m Resolution)")
    
    # Initialize Map with specific Google Satellite background
    m = leafmap.Map(center=[coords["lat"], coords["lon"]], zoom=12)
    m.add_basemap("SATELLITE")
    
    # Force visibility with opacity: 1.0
    vis = {
        "min": stats["vis_min"], 
        "max": stats["vis_max"], 
        "palette": stats["palette"],
        "opacity": 0.8  # Semi-transparent so you can see the streets underneath
    }
    
    # Add layers to the map
    # Note: Using .add_ee_layer is the standard for leafmap.foliumap
    m.add_ee_layer(current_lst, vis, "2024 Baseline")
    m.add_ee_layer(forecast_2026, vis, "2026 Prediction")
    
    # ADD THE COLORBAR (The Scale)
    m.add_colorbar(
        colors=stats["palette"],
        vmin=stats["vis_min"],
        vmax=stats["vis_max"],
        label="Surface Temperature (°F)",
        orientation="horizontal",
        position="bottomright"
    )

    # Force the Layer Control to appear (so you can toggle UHI on/off manually)
    m.add_layer_control()
    
    # RENDER: Using a unique key for the city ensures the map refreshes correctly
    m.to_streamlit(height=700, key=f"map_{selected_city.replace(',', '').replace(' ', '_')}")

    # 8. AI INSIGHTS BOTTOM BAR
    st.info(f"**Methodology Note:** Thermal data is derived from Landsat 8/9 Collection 2 Level 2 (ST_B10) resampled with MODIS Aqua (MYD11A2) robust linear regression.")

else:
    st.error("Engine failed to synchronize with Earth Engine. Check your Service Account permissions.")
