import streamlit as st
import leafmap.foliumap as leafmap
import os
import sys

# 1. DYNAMIC PATH FIX
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from src.engine import get_gee_data

st.set_page_config(page_title="Urban Heat Agent 2026", layout="wide", page_icon="🔥")

# High-Contrast CSS for Metrics
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

CITIES = {
    "Atlanta, GA": {"lat": 33.7490, "lon": -84.3880},
    "New York, NY": {"lat": 40.7128, "lon": -74.0060},
    "Phoenix, AZ": {"lat": 33.4484, "lon": -112.0740},
    "Chicago, IL": {"lat": 41.8781, "lon": -87.6298}
}

st.sidebar.title("🏙️ Heat Agent v4.3")
selected_city = st.sidebar.selectbox("Select Target City", list(CITIES.keys()))
coords = CITIES[selected_city]

with st.spinner("Analyzing satellite thermal stacks..."):
    stats = get_gee_data(selected_city, coords["lon"], coords["lat"])

if stats:
    st.title(f"Thermal Analysis: {selected_city}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Baseline Temp", f"{stats['mean_temp_f']}°F")
    col2.metric("Warming Trend", f"{stats['warming_trend']}°F/yr")
    
    gain = round(stats['pred_2026_f'] - stats['mean_temp_f'], 2)
    col3.metric("2026 Forecast", f"{stats['pred_2026_f']}°F", delta=f"{gain}°F")

    st.markdown("---")

    # The Map with pre-rendered tiles
    m = leafmap.Map(center=[coords["lat"], coords["lon"]], zoom=12)
    m.add_basemap("SATELLITE")
    
    # Pre-colored tiles from GEE
    m.add_tile_layer(
        url=stats["current_url"], 
        name="2024 Baseline", 
        attribution="Google Earth Engine", 
        opacity=0.6
    )
    m.add_tile_layer(
        url=stats["forecast_url"], 
        name="2026 Prediction", 
        attribution="Google Earth Engine", 
        opacity=0.7
    )
    
    # Legend for UI reference
    m.add_colorbar(
        colors=['#0000ff', '#ffff00', '#ff0000'],
        vmin=85, vmax=115,
        label="Surface Temp (°F)",
        orientation="horizontal",
        position="bottomright"
    )
    
    m.add_layer_control()
    m.to_streamlit(height=700, key=f"map_{selected_city.replace(' ', '')}")

    st.info("💡 Pro-tip: Open the layer control icon in the top right to toggle between years.")

else:
    st.error("Engine failed to synchronize. Please check Streamlit Secrets for GEE credentials.")
