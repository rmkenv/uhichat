import streamlit as st
import leafmap.foliumap as leafmap
import sys
import os

# Ensure src module is findable
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.engine import get_gee_data

st.set_page_config(page_title="Heat Agent 2026", layout="wide", page_icon="🔥")

# High-Contrast CSS
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
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

st.sidebar.title("🏙️ Heat Agent v4.0")
selected = st.sidebar.selectbox("Select Target City", list(CITIES.keys()))
coords = CITIES[selected]

with st.spinner("Analyzing satellite thermal stacks..."):
    geom, stats = get_gee_data(selected, coords["lon"], coords["lat"])

if stats:
    st.title(f"Thermal Forecast: {selected}")
    
    # METRICS
    c1, c2, c3 = st.columns(3)
    c1.metric("Baseline Temp", f"{stats['mean_temp_f']}°F")
    c2.metric("Warming Trend", f"{stats['warming_trend']}°F/yr")
    gain = round(stats['pred_2026_f'] - stats['mean_temp_f'], 2)
    c3.metric("2026 Forecast", f"{stats['pred_2026_f']}°F", delta=f"{gain}°F Gain")

    st.markdown("---")

    # THE MAP
    st.subheader("Interactive Heat Map (30m Resolution)")
    m = leafmap.Map(center=[coords["lat"], coords["lon"]], zoom=12)
    m.add_basemap("SATELLITE")
    
    # Direct Tile Injection
    m.add_tile_layer(url=stats["current_tile_url"], name="2024 Baseline", opacity=0.6)
    m.add_tile_layer(url=stats["forecast_tile_url"], name="2026 Prediction", opacity=0.7)
    
    # Colorbar Scale
    m.add_colorbar(
        colors=['#0000ff', '#ffff00', '#ff0000'],
        vmin=85, vmax=115,
        label="Surface Temp (°F)",
        orientation="horizontal",
        position="bottomright"
    )
    
    m.add_layer_control()
    m.to_streamlit(height=700, key=f"map_v4_{selected.replace(' ', '')}")

    st.info("💡 Pro-tip: Open the layer control (top right) to toggle between the current baseline and the 2026 prediction.")

else:
    st.error("Data retrieval failed. Please check your credentials and city coordinates.")
