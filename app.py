import streamlit as st
import leafmap.foliumap as leafmap
import os
import sys

# 1. DYNAMIC PATH FIX (Ensures src.engine is importable on Cloud)
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from src.engine import get_gee_data

# 2. PAGE CONFIG
st.set_page_config(page_title="Urban Heat Agent 2026", layout="wide", page_icon="🔥")

# 3. HIGH-CONTRAST CSS
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 10px !important;
        padding: 15px !important;
    }
    [data-testid="stMetricLabel"] { color: #475569 !important; font-weight: 600 !important; }
    [data-testid="stMetricValue"] { color: #1e293b !important; font-weight: 800 !important; }
    </style>
    """, unsafe_allow_html=True)

# 4. SIDEBAR - CONTROLS & REPO LINK
st.sidebar.title("🏙️ Heat Agent v4.4")
st.sidebar.markdown("[🔗 View GitHub Repo](https://github.com/rmkenv/uhichat)")
st.sidebar.markdown("---")

st.sidebar.subheader("Map Settings")
# Opacity Sliders
base_op = st.sidebar.slider("2024 Baseline Opacity", 0.0, 1.0, 0.6, 0.05)
pred_op = st.sidebar.slider("2026 Forecast Opacity", 0.0, 1.0, 0.7, 0.05)

CITIES = {
    "Atlanta, GA": {"lat": 33.7490, "lon": -84.3880},
    "New York, NY": {"lat": 40.7128, "lon": -74.0060},
    "Phoenix, AZ": {"lat": 33.4484, "lon": -112.0740},
    "Chicago, IL": {"lat": 41.8781, "lon": -87.6298}
}

selected_city = st.sidebar.selectbox("Select Target City", list(CITIES.keys()))
coords = CITIES[selected_city]

# 5. DATA PROCESSING
with st.spinner(f"Analyzing thermal stacks for {selected_city}..."):
    stats = get_gee_data(selected_city, coords["lon"], coords["lat"])

# 6. MAIN UI RENDER
if stats:
    st.title(f"Thermal Analysis: {selected_city}")
    
    # Metrics Row
    col1, col2, col3 = st.columns(3)
    col1.metric("Baseline Temp", f"{stats['mean_temp_f']}°F")
    col2.metric("Warming Trend", f"{stats['warming_trend']}°F/yr")
    
    gain = round(stats['pred_2026_f'] - stats['mean_temp_f'], 2)
    col3.metric("2026 Forecast", f"{stats['pred_2026_f']}°F", delta=f"{gain}°F")

    st.markdown("---")

    # The Map
    m = leafmap.Map(center=[coords["lat"], coords["lon"]], zoom=12)
    m.add_basemap("SATELLITE")
    
    # Layer 1: 2024 Baseline
    m.add_tile_layer(
        url=stats["current_url"], 
        name="2024 Baseline", 
        attribution="Google Earth Engine", 
        opacity=base_op
    )
    
    # Layer 2: 2026 Prediction
    m.add_tile_layer(
        url=stats["forecast_url"], 
        name="2026 Prediction", 
        attribution="Google Earth Engine", 
        opacity=pred_op
    )
    
    # Static Legend
    m.add_colorbar(
        colors=['#0000ff', '#ffff00', '#ff0000'],
        vmin=85, vmax=115,
        label="Surface Temp (°F)",
        orientation="horizontal",
        position="bottomright"
    )
    
    m.add_layer_control()
    
    # CRITICAL: unique key per opacity setting prevents stale map state
    map_key = f"map_{selected_city.replace(' ', '')}_{base_op}_{pred_op}"
    m.to_streamlit(height=700, key=map_key)

    st.info("💡 **User Guide:** Use the sliders in the sidebar to 'look through' the heat layers to the satellite imagery below. This helps identify specific heat-retaining structures like parking lots and dark rooftops.")

else:
    st.error("Engine failed to synchronize. Please check Streamlit Secrets for GEE credentials.")
