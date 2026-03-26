# CSS FIX: Explicitly set background AND text color for readability
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    
    /* Target the Metric Containers */
    [data-testid="stMetric"] {
        background-color: #ffffff !important;
        padding: 20px !important;
        border-radius: 10px !important;
        border: 1px solid #d1d5db !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }

    /* Force Label and Value text to be dark/readable */
    [data-testid="stMetricLabel"] {
        color: #374151 !important;
        font-weight: 600 !important;
    }
    [data-testid="stMetricValue"] {
        color: #111827 !important;
    }
    </style>
    """, unsafe_allow_html=True)

import streamlit as st
import pandas as pd
import leafmap.foliumap as leafmap
import sys
import os

# PATH FIX: Ensure the app can see the 'src' folder
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.engine import get_gee_data

st.set_page_config(page_title="Urban Heat Agent 2026", layout="wide", page_icon="🔥")

# CSS FIX: Corrected argument name to unsafe_allow_html
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e6ed; }
    </style>
    """, unsafe_allow_html=True)

st.sidebar.title("🏙️ Heat Agent")
CITIES = {
    "Atlanta, GA": {"lat": 33.7490, "lon": -84.3880},
    "New York, NY": {"lat": 40.7128, "lon": -74.0060},
    "Phoenix, AZ": {"lat": 33.4484, "lon": -112.0740}
}

selected = st.sidebar.selectbox("City Selection", list(CITIES.keys()))
c = CITIES[selected]

with st.spinner("Analyzing satellite stacks..."):
    geom, current, forecast, stats, thumb = get_gee_data(selected, c["lon"], c["lat"])

if stats:
    col1, col2, col3 = st.columns(3)
    col1.metric("Baseline Temp", f"{stats['mean_temp_f']}°F")
    col2.metric("Warming Trend", f"{stats['warming_trend']}°F/yr")
    col3.metric("2026 Forecast", f"{stats['pred_2026_f']}°F", 
                delta=f"{round(stats['pred_2026_f'] - stats['mean_temp_f'], 1)}°F Gain")

    m = leafmap.Map(center=[c["lat"], c["lon"]], zoom=12)
    m.add_basemap("SATELLITE")
    v = {"min": 85, "max": 115, "palette": ['blue', 'yellow', 'red']}
    m.add_ee_layer(current, v, "2024 Baseline (30m)")
    m.add_ee_layer(forecast, v, "2026 Prediction (30m)")
    m.to_streamlit(height=600)
else:
    st.error("Could not load data. Check Earth Engine credentials.")
