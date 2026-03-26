import streamlit as st
import pandas as pd
import leafmap.foliumap as leafmap
import sys
import os

# 1. PATH FIX: Ensures the app can see the 'src' folder in Streamlit Cloud
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.engine import get_gee_data

# 2. PAGE CONFIGURATION
st.set_page_config(
    page_title="Urban Heat Agent 2026",
    layout="wide",
    page_icon="🔥"
)

# 3. HIGH-CONTRAST CSS (Fixes the "White on White" readability issue)
st.markdown("""
    <style>
    /* Background of the main app */
    .main { background-color: #f8fafc; }

    /* Metric Card Styling */
    [data-testid="stMetric"] {
        background-color: #ffffff !important;
        padding: 20px !important;
        border-radius: 12px !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
    }

    /* Force DARK text for Label (Title) */
    [data-testid="stMetricLabel"] {
        color: #475569 !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
    }

    /* Force DARK text for Value (The Temp/Number) */
    [data-testid="stMetricValue"] {
        color: #1e293b !important;
        font-size: 2.2rem !important;
        font-weight: 700 !important;
    }
    
    /* Delta (The Gain/Loss) */
    [data-testid="stMetricDelta"] {
        font-weight: 500 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# 4. SIDEBAR SETUP
st.sidebar.title("🏙️ Heat Agent v2.0")
st.sidebar.markdown("---")

CITIES = {
    "Atlanta, GA": {"lat": 33.7490, "lon": -84.3880},
    "New York, NY": {"lat": 40.7128, "lon": -74.0060},
    "Phoenix, AZ": {"lat": 33.4484, "lon": -112.0740},
    "Chicago, IL": {"lat": 41.8781, "lon": -87.6298},
    "Los Angeles, CA": {"lat": 34.0522, "lon": -118.2437}
}

selected_city = st.sidebar.selectbox("Select Target City", list(CITIES.keys()))
city_coords = CITIES[selected_city]

st.sidebar.info("""
**Engine Specs:**
* **Trend:** 22-Year MODIS (1km)
* **Baseline:** 5-Year Landsat (30m)
* **Target:** Summer 2026 Projection
""")

# 5. DATA FETCHING
with st.spinner(f"Analyzing {selected_city} satellite stacks..."):
    geometry, current_lst, forecast_2026, stats, thumb_url = get_gee_data(
        selected_city, city_coords["lon"], city_coords["lat"]
    )

# 6. DASHBOARD RENDERING
if stats:
    st.title(f"Thermal Analysis: {selected_city}")
    
    # METRICS ROW
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="Baseline Surface Temp", 
            value=f"{stats['mean_temp_f']}°F",
            help="Neighborhood-scale (30m) median temperature from 2020-2025."
        )
    
    with col2:
        st.metric(
            label="22-Year Warming Trend", 
            value=f"{stats['warming_trend']}°F/yr",
            delta="Statistically Significant",
            delta_color="inverse"
        )
    
    with col3:
        # Calculate Delta for visual feedback
        gain = round(stats['pred_2026_f'] - stats['mean_temp_f'], 2)
        st.metric(
            label="2026 Forecast", 
            value=f"{stats['pred_2026_f']}°F", 
            delta=f"{gain}°F Total Gain"
        )

    st.markdown("---")

    # MAP AND INSIGHTS ROW
    m_col, d_col = st.columns([2, 1])

    with m_col:
        st.subheader("Interactive Heat Mapping")
        m = leafmap.Map(center=[city_coords["lat"], city_coords["lon"]], zoom=12)
        m.add_basemap("SATELLITE")
        
        # Visual Parameters
        vis_params = {
            "min": 85, 
            "max": 115, 
            "palette": ['#0000ff', '#ffff00', '#ff0000']
        }
        
        m.add_ee_layer(current_lst, vis_params, "2024 Baseline (30m)")
        m.add_ee_layer(forecast_2026, vis_params, "2026 Prediction (30m)")
        
        m.to_streamlit(height=600)

    with d_col:
        st.subheader("AI Insight Packet")
        st.image(thumb_url, caption="Thermal Remote Sensing Thumbnail", use_column_width=True)
        
        st.write(f"**Regional Climate Report:**")
        st.write(f"Based on historical MODIS data, {selected_city} is warming at a rate of **{stats['warming_trend']}°F per year**.")
        
        if stats['warming_trend'] > 0.08:
            st.error("⚠️ RAPID WARMING: This city exceeds the national average warming rate.")
        elif stats['warming_trend'] > 0.04:
            st.warning("📊 STEADY WARMING: Standard urban climate escalation detected.")
        else:
            st.success("✅ STABLE TREND: Warming rates are below critical urban thresholds.")

        # Data Export
        df = pd.DataFrame([stats])
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Heat Report (CSV)",
            data=csv,
            file_name=f"{selected_city.replace(' ', '_')}_report.csv",
            mime="text/csv",
        )

else:
    st.error("Engine failed to initialize. Please check Google Earth Engine credentials or selection bounds.")

st.sidebar.markdown("---")
st.sidebar.caption("Data Source: NASA/USGS Landsat 8/9 & MODIS Aqua (MYD11A2)")
