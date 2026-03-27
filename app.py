import streamlit as st
import pandas as pd
import leafmap.foliumap as leafmap
import sys
import os

# PATH FIX
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.engine import get_gee_data

st.set_page_config(page_title="Heat Agent 2026", layout="wide", page_icon="🔥")

# HIGH-CONTRAST CSS
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
    [data-testid="stMetricValue"] { color: #1e293b !important; font-weight: 700 !important; }
    </style>
    """, unsafe_allow_html=True)

st.sidebar.title("🏙️ Heat Agent v2.1")
CITIES = {
    "Atlanta, GA": {"lat": 33.7490, "lon": -84.3880},
    "New York, NY": {"lat": 40.7128, "lon": -74.0060},
    "Phoenix, AZ": {"lat": 33.4484, "lon": -112.0740},
    "Chicago, IL": {"lat": 41.8781, "lon": -87.6298}
}

selected_city = st.sidebar.selectbox("Select City", list(CITIES.keys()))
coords = CITIES[selected_city]

with st.spinner(f"Analyzing {selected_city}..."):
    geom, current_lst, forecast_2026, stats, thumb_url = get_gee_data(
        selected_city, coords["lon"], coords["lat"]
    )

if stats:
    st.title(f"Thermal Analysis: {selected_city}")
    
    # METRICS
    c1, c2, c3 = st.columns(3)
    c1.metric("Baseline Temp", f"{stats['mean_temp_f']}°F")
    c2.metric("Warming Trend", f"{stats['warming_trend']}°F/yr")
    gain = round(stats['pred_2026_f'] - stats['mean_temp_f'], 2)
    c3.metric("2026 Forecast", f"{stats['pred_2026_f']}°F", delta=f"{gain}°F Gain")

    st.markdown("---")

    # MAP
    m_col, d_col = st.columns([2, 1])
    with m_col:
        st.subheader("Interactive Heat Mapping")
        m = leafmap.Map(center=[coords["lat"], coords["lon"]], zoom=12)
        m.add_basemap("SATELLITE")
        
        vis = {"min": stats["vis_min"], "max": stats["vis_max"], "palette": stats["palette"]}
        m.add_ee_layer(current_lst, vis, "2024 Baseline (30m)")
        m.add_ee_layer(forecast_2026, vis, "2026 Prediction (30m)")
        
        # ADD THE COLORBAR SCALE
        m.add_colorbar(
            colors=stats["palette"],
            vmin=stats["vis_min"],
            vmax=stats["vis_max"],
            label="Surface Temperature (°F)",
            orientation="horizontal"
        )
        m.to_streamlit(height=600)

    with d_col:
        st.subheader("AI Insight Packet")
        st.image(thumb_url, caption="2026 Forecast Thumbnail", use_column_width=True)
        st.write(f"Trend: **{stats['warming_trend']}°F/year**")
        if stats['warming_trend'] > 0.08:
            st.error("⚠️ RAPID WARMING DETECTED")
        else:
            st.success("✅ STABLE URBAN CLIMATE")
