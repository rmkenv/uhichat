import streamlit as st
import pandas as pd
import leafmap.foliumap as leafmap
from src.engine import get_gee_data

# 1. PAGE CONFIG
st.set_page_config(page_title="Urban Heat Agent 2026", layout="wide", page_icon="🔥")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e6ed; }
    </style>
    """, unsafe_content_as_none=True)

# 2. SIDEBAR & CITY CONFIG
st.sidebar.title("🏙️ Urban Heat Agent")
st.sidebar.info("Two-Layer Analysis: MODIS (22-yr Trend) + Landsat (30m Baseline)")

# Hardcoded Cities from your GEE Logic
CITIES = {
    "Atlanta, GA": {"lat": 33.7490, "lon": -84.3880},
    "New York, NY": {"lat": 40.7128, "lon": -74.0060},
    "Phoenix, AZ": {"lat": 33.4484, "lon": -112.0740},
    "Chicago, IL": {"lat": 41.8781, "lon": -87.6298},
    "Los Angeles, CA": {"lat": 34.0522, "lon": -118.2437}
}

selected_city = st.sidebar.selectbox("Select Target City", list(CITIES.keys()))
city_coords = CITIES[selected_city]

# 3. DATA PROCESSING
with st.spinner(f"Analyzing {selected_city} (22-year historical stack)..."):
    geometry, current_lst, forecast_2030, stats, thumb_url = get_gee_data(
        selected_city, city_coords["lon"], city_coords["lat"]
    )

if stats:
    # 4. DASHBOARD LAYOUT
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Avg Surface Temp", f"{stats['mean_temp_f']}°F", delta="Current Baseline")
    with col2:
        st.metric("22-Yr Warming Rate", f"{stats['warming_trend']}°F/yr", delta="Statistically Significant", delta_color="inverse")
    with col3:
        # SUHI Metric (Heat Burden above green baseline)
        st.metric("Urban Heat Intensity", f"+{stats['suhi_intensity']}°F", help="How much hotter the city core is compared to surrounding parks/trees.")
    with col4:
        st.metric("2026 Prediction", f"{stats['pred_2026_f']}°F", delta=f"{round(stats['pred_2026_f'] - stats['mean_temp_f'], 2)}°F Gain")

    st.divider()

    # 5. INTERACTIVE MAP
    m_col, d_col = st.columns([2, 1])

    with m_col:
        st.subheader(f"Neighborhood Heat Mapping: {selected_city}")
        m = leafmap.Map(center=[city_coords["lat"], city_coords["lon"]], zoom=12)
        m.add_basemap("SATELLITE")
        
        # Add GEE Layers with your custom Palette
        vis_params = {"min": 85, "max": 115, "palette": ['040274','307ef3','3be285','fff705','ff8b13','de0101']}
        
        m.add_ee_layer(current_lst, vis_params, "Current Surface Temp (30m)")
        m.add_ee_layer(forecast_2030, vis_params, "Predicted 2026 Temp (30m)")
        
        m.to_streamlit(height=600)

    with d_col:
        st.subheader("AI Insight Packet")
        st.image(thumb_url, caption="Thermal Remote Sensing Thumbnail", use_column_width=True)
        
        st.write(f"**Analysis for {selected_city}:**")
        st.write(f"The warming trend of **{stats['warming_trend']}°F/year** suggests a total surface gain of nearly **{round(stats['warming_trend'] * 10, 2)}°F** per decade.")
        
        if stats['suhi_intensity'] > 10:
            st.error(f"⚠️ HIGH HEAT BURDEN: {selected_city} shows an Urban Heat Island intensity of {stats['suhi_intensity']}°F above its rural baseline. Immediate cooling interventions (cool roofs, greening) recommended.")
        else:
            st.success(f"✅ MODERATE HEAT BURDEN: {selected_city} maintains a cooling buffer from local green space.")

        # Download Data Button
        csv = pd.DataFrame([stats]).to_csv(index=False).encode('utf-8')
        st.download_button("Download Analysis (CSV)", csv, f"{selected_city}_heat_report.csv", "text/csv")

else:
    st.error("Failed to retrieve satellite data. Please check Earth Engine permissions or AOI coverage.")

st.sidebar.markdown("---")
st.sidebar.caption("Data: NASA/USGS Landsat 8/9 & MODIS Aqua (MYD11A2)")
