import streamlit as st
import leafmap.foliumap as leafmap
import os
import sys

# 1. DYNAMIC PATH FIX
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

# 4. SIDEBAR - TOP 25 CITIES DATA
st.sidebar.title("🏙️ Heat Agent v5.1")
st.sidebar.markdown("[🔗 GitHub Repo](https://github.com/rmkenv/uhichat)")
st.sidebar.markdown("---")

# Expanded City List (Top 25 US by Population)
CITIES = {
    "New York, NY": {"lat": 40.7128, "lon": -74.0060},
    "Los Angeles, CA": {"lat": 34.0522, "lon": -118.2437},
    "Chicago, IL": {"lat": 41.8781, "lon": -87.6298},
    "Houston, TX": {"lat": 29.7604, "lon": -95.3698},
    "Phoenix, AZ": {"lat": 33.4484, "lon": -112.0740},
    "Philadelphia, PA": {"lat": 39.9526, "lon": -75.1652},
    "San Antonio, TX": {"lat": 29.4241, "lon": -98.4936},
    "San Diego, CA": {"lat": 32.7157, "lon": -117.1611},
    "Dallas, TX": {"lat": 32.7767, "lon": -96.7970},
    "San Jose, CA": {"lat": 37.3382, "lon": -121.8863},
    "Austin, TX": {"lat": 30.2672, "lon": -97.7431},
    "Jacksonville, FL": {"lat": 30.3322, "lon": -81.6557},
    "Fort Worth, TX": {"lat": 32.7555, "lon": -97.3308},
    "Columbus, OH": {"lat": 39.9612, "lon": -82.9988},
    "Indianapolis, IN": {"lat": 39.7684, "lon": -86.1581},
    "Charlotte, NC": {"lat": 35.2271, "lon": -80.8431},
    "San Francisco, CA": {"lat": 37.7749, "lon": -122.4194},
    "Seattle, WA": {"lat": 47.6062, "lon": -122.3321},
    "Denver, CO": {"lat": 39.7392, "lon": -104.9903},
    "Washington, DC": {"lat": 38.9072, "lon": -77.0369},
    "Nashville, TN": {"lat": 36.1627, "lon": -86.7816},
    "Oklahoma City, OK": {"lat": 35.4676, "lon": -97.5164},
    "El Paso, TX": {"lat": 31.7619, "lon": -106.4850},
    "Boston, MA": {"lat": 42.3601, "lon": -71.0589},
    "Portland, OR": {"lat": 45.5152, "lon": -122.6784}
}

selected_city = st.sidebar.selectbox("Select Target City", sorted(list(CITIES.keys())))
coords = CITIES[selected_city]

st.sidebar.subheader("Layer Opacity")
base_op = st.sidebar.slider("2024 Baseline", 0.0, 1.0, 0.6, 0.05)
pred_op = st.sidebar.slider("2026 Forecast", 0.0, 1.0, 0.7, 0.05)

# Sidebar Methodology Snippet
with st.sidebar.expander("📖 Methodology"):
    st.write("""
    **Data Sources:**
    * **Landsat 8/9 (30m):** Used for street-level thermal baselines.
    * **MODIS (1km):** 22-year daily stack used to calculate regional warming trends.
    
    **Calculation:**
    The 2026 projection is derived by applying a pixel-level **Robust Linear Regression (Sen's Slope)** from 2003–2025 to the current high-resolution thermal baseline.
    """)

# 5. DATA PROCESSING
with st.spinner(f"Analyzing {selected_city}..."):
    stats = get_gee_data(selected_city, coords["lon"], coords["lat"])

# 6. UI RENDER
if stats:
    st.title(f"Thermal Analysis: {selected_city}")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Baseline Temp", f"{stats['mean_temp_f']}°F")
    m2.metric("Warming Trend", f"{stats['warming_trend']}°F/yr")
    gain = round(stats['pred_2026_f'] - stats['mean_temp_f'], 2)
    m3.metric("2026 Forecast", f"{stats['pred_2026_f']}°F", delta=f"{gain}°F")

    st.markdown("---")

    # Map with Dynamic Key for Opacity refreshes
    m = leafmap.Map(center=[coords["lat"], coords["lon"]], zoom=11)
    m.add_basemap("SATELLITE")
    
    m.add_tile_layer(url=stats["current_url"], name="2024 Baseline", attribution="GEE", opacity=base_op)
    m.add_tile_layer(url=stats["forecast_url"], name="2026 Prediction", attribution="GEE", opacity=pred_op)
    
    m.add_colorbar(
        colors=['#0000ff', '#ffff00', '#ff0000'],
        vmin=85, vmax=115,
        label="Surface Temp (°F)",
        orientation="horizontal",
        position="bottomright"
    )
    
    m.add_layer_control()
    
    # Unique key ensures map re-renders when city OR opacity changes
    map_key = f"v5_map_{selected_city.replace(' ', '')}_{base_op}_{pred_op}"
    m.to_streamlit(height=700, key=map_key)

    # 7. EXPANDED METHODOLOGY SECTION
    st.markdown("---")
    with st.expander("🔬 Detailed Scientific Methodology"):
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("""
            ### 1. Multi-Decadal Trend Analysis
            We ingest the entire **MODIS (MYD11A2.061)** daytime Land Surface Temperature archive from 2003 to the present. 
            By applying a **Sen's Slope** estimator, we filter out seasonal noise to find the true underlying warming trend per pixel.
            """)
        with col_b:
            st.markdown("""
            ### 2. High-Resolution Fusion
            While MODIS provides the trend, its 1km resolution is too coarse for urban planning. We fuse this trend with **Landsat 8 & 9 (Collection 2 Level 2)** thermal data. 
            This allows us to project heat risks at a **30-meter resolution**, identifying specific parking lots, rooftops, and parks.
            """)
        
        st.latex(r"T_{2026} = T_{baseline} + (Slope_{2003-2025} \times 2)")

else:
    st.error("Engine failed. Check GEE credentials or coordinate bounds.")
