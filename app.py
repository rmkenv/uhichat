import streamlit as st
import leafmap.foliumap as leafmap
import sys
import os

# Ensures the 'src' module is findable
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.engine import get_gee_data

st.set_page_config(page_title="Heat Agent 2026", layout="wide", page_icon="🔥")

# FORCE CONTRAST CSS (Fixes "ghost" text in Metrics)
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 12px !important;
        padding: 15px !important;
    }
    [data-testid="stMetricLabel"] { color: #334155 !important; font-weight: 600 !important; }
    [data-testid="stMetricValue"] { color: #0f172a !important; font-weight: 800 !important; }
    </style>
    """, unsafe_allow_html=True)

CITIES = {
    "Atlanta, GA": {"lat": 33.7490, "lon": -84.3880},
    "New York, NY": {"lat": 40.7128, "lon": -74.0060},
    "Phoenix, AZ": {"lat": 33.4484, "lon": -112.0740},
    "Chicago, IL": {"lat": 41.8781, "lon": -87.6298}
}

st.sidebar.title("🏙️ Heat Agent 2026")
selected = st.sidebar.selectbox("Select Target City", list(CITIES.keys()))
coords = CITIES[selected]

with st.spinner(f"Retrieving thermal data for {selected}..."):
    geom, current, forecast, stats = get_gee_data(selected, coords["lon"], coords["lat"])

if stats:
    st.title(f"Thermal Forecast: {selected}")
    
    # METRICS ROW
    c1, c2, c3 = st.columns(3)
    c1.metric("Baseline Temp", f"{stats['mean_temp_f']}°F")
    c2.metric("Warming Trend", f"{stats['warming_trend']}°F/yr")
    c3.metric("2026 Forecast", f"{stats['pred_2026_f']}°F", 
              delta=f"{round(stats['pred_2026_f'] - stats['mean_temp_f'], 2)}°F")

    st.markdown("---")

    # THE MAP
    m = leafmap.Map(center=[coords["lat"], coords["lon"]], zoom=12)
    m.add_basemap("SATELLITE")
    
    vis = {"min": stats["vis_min"], "max": stats["vis_max"], "palette": stats["palette"]}
    
    # Adding data layers
    m.add_ee_layer(current, vis, "2024 Baseline (30m)")
    m.add_ee_layer(forecast, vis, "2026 Prediction (30m)")
    
    # 🌈 THE COLORBAR (The Scale)
    m.add_colorbar(
        colors=stats["palette"],
        vmin=stats["vis_min"],
        vmax=stats["vis_max"],
        label="Surface Temperature (°F)",
        orientation="horizontal",
        position="bottomright",
        layer_name="Heat Scale"
    )
    
    m.to_streamlit(height=700)

else:
    st.error("Engine failed. Check GEE credentials or city coordinates.")
