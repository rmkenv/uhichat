import streamlit as st
import leafmap.foliumap as leafmap
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.engine import get_gee_data

st.set_page_config(page_title="Heat Agent 2026", layout="wide", page_icon="🔥")

# CSS for Dark Text on White Cards
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
    }
    [data-testid="stMetricLabel"] { color: #475569 !important; font-weight: 600 !important; }
    [data-testid="stMetricValue"] { color: #1e293b !important; font-weight: 700 !important; }
    </style>
    """, unsafe_allow_html=True)

CITIES = {
    "Atlanta, GA": {"lat": 33.7490, "lon": -84.3880},
    "New York, NY": {"lat": 40.7128, "lon": -74.0060},
    "Phoenix, AZ": {"lat": 33.4484, "lon": -112.0740}
}

selected = st.sidebar.selectbox("Select City", list(CITIES.keys()))
coords = CITIES[selected]

with st.spinner("Analyzing satellite stacks..."):
    geom, current, forecast, stats = get_gee_data(selected, coords["lon"], coords["lat"])

if stats:
    # 1. TOP METRICS
    c1, c2, c3 = st.columns(3)
    c1.metric("Baseline Temp", f"{stats['mean_temp_f']}°F")
    c2.metric("Warming Trend", f"{stats['warming_trend']}°F/yr")
    c3.metric("2026 Forecast", f"{stats['pred_2026_f']}°F")

    st.markdown("---")

    # 2. THE MAP WITH COLORBAR
    st.subheader(f"Interactive Thermal Forecast: {selected}")
    m = leafmap.Map(center=[coords["lat"], coords["lon"]], zoom=12)
    m.add_basemap("SATELLITE")
    
    vis = {"min": stats["vis_min"], "max": stats["vis_max"], "palette": stats["palette"]}
    
    # Adding the GEE layers
    m.add_ee_layer(current, vis, "2024 Baseline (30m)")
    m.add_ee_layer(forecast, vis, "2026 Prediction (30m)")
    
    # ADDING THE THUMBNAIL SCALE (COLORBAR)
    m.add_colorbar(
        colors=stats["palette"],
        vmin=stats["vis_min"],
        vmax=stats["vis_max"],
        label="Surface Temperature (°F)",
        orientation="horizontal",
        transparent_bg=True
    )
    
    m.to_streamlit(height=700)
