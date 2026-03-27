import streamlit as st
import leafmap.foliumap as leafmap
import sys
import os

# 1. PATH FIX: Ensures the app can find the 'src' folder
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.engine import get_gee_data

# 2. PAGE CONFIG
st.set_page_config(page_title="Urban Heat Agent 2026", layout="wide", page_icon="🔥")

# 3. HIGH-CONTRAST CSS: Fixes readability for Metrics
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

# 4. SIDEBAR SETUP
st.sidebar.title("🏙️ Heat Agent v3.0")
st.sidebar.markdown("---")

CITIES = {
    "Atlanta, GA": {"lat": 33.7490, "lon": -84.3880},
    "New York, NY": {"lat": 40.7128, "lon": -74.0060},
    "Phoenix, AZ": {"lat": 33.4484, "lon": -112.0740},
    "Chicago, IL": {"lat": 41.8781, "lon": -87.6298},
    "Los Angeles, CA": {"lat": 34.0522, "lon": -118.2437}
}

selected_city = st.sidebar.selectbox("Select Target City", list(CITIES.keys()))
coords = CITIES[selected_city]

# 5. DATA FETCHING (Now receiving Tile URLs)
with st.spinner(f"Fetching Tile URLs for {selected_city}..."):
    geometry, stats = get_gee_data(selected_city, coords["lon"], coords["lat"])

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

    # 7. THE MAP (The URL-Injected Fix)
    st.subheader("Interactive Heat Mapping (Direct Tile Injection)")
    
    # Initialize Map
    m = leafmap.Map(center=[coords["lat"], coords["lon"]], zoom=12)
    m.add_basemap("SATELLITE")
    
    # Inject the pre-signed Tile URLs directly
    # This bypasses the Earth Engine Python-to-JS handshake
    m.add_tile_layer(
        url=stats["current_tile_url"], 
        name="2024 Baseline (30m)", 
        attribution="Google Earth Engine / NASA / USGS",
        opacity=0.7
    )
    
    m.add_tile_layer(
        url=stats["forecast_tile_url"], 
        name="2026 Prediction (30m)", 
        attribution="Google Earth Engine / NASA / USGS",
        opacity=0.8
    )
    
    # ADD THE COLORBAR (The Scale)
    m.add_colorbar(
        colors=stats["palette"],
        vmin=stats["vis_min"],
        vmax=stats["vis_max"],
        label="Surface Temperature (°F)",
        orientation="horizontal",
        position="bottomright"
    )

    # Force Layer Control so you can toggle between Baseline and Forecast
    m.add_layer_control()
    
    # Render with unique city key
    m.to_streamlit(height=700, key=f"v3_map_{selected_city.replace(' ', '_')}")

    # 8. AI INSIGHTS
    st.markdown("### 🔍 Analysis Report")
    if stats['warming_trend'] > 0.08:
        st.error(f"**High Warming Rate:** {selected_city} is warming significantly faster than rural baselines.")
    else:
        st.success(f"**Stable Urban Growth:** {selected_city} shows standard thermal escalation patterns.")

else:
    st.error("Engine failed to generate Tile URLs. Please check your GEE Service Account quotas.")
