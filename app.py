import streamlit as st
import leafmap.foliumap as lm
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderUnavailable
from google.genai import client
import os

# Internal imports
from src.engine import get_gee_data, initialize_ee
from src.agent import ask_gemini

# 1. Page Configuration
st.set_page_config(
    page_title="Climate Intelligence Agent",
    page_icon="🌍",
    layout="wide"
)

st.title("🌍 Gemini 3 Climate Intelligence")
st.markdown("---")

# 2. Initialize Earth Engine
# This handles the PEM cleaning and Scopes we fixed in engine.py
initialize_ee()

# 3. Initialize Gemini AI Client
if "gemini_client" not in st.session_state:
    st.session_state.gemini_client = client.Client(api_key=st.secrets["GEMINI_API_KEY"])

# 4. Sidebar UI
with st.sidebar:
    st.header("🔍 Analysis Settings")
    city_input = st.text_input("Enter City & State", "Phoenix, AZ")
    
    st.info("""
    **Satellite Sources:**
    * MODIS (20-year Thermal Trends)
    * Landsat 8/9 (30m High-Res)
    * Gemini 3 (Predictive Analysis)
    """)
    
    run_analysis = st.button("Generate Intelligence Report", type="primary")

# 5. Main Layout
col_map, col_ai = st.columns([1.5, 1])

if run_analysis:
    with st.spinner(f"📡 Locating {city_input} and fetching orbital data..."):
        
        # --- FIX: Robust Geocoding with Timeout and Unique Agent ---
        # Nominatim requires a unique user_agent to avoid being rate-limited
        geolocator = Nominatim(user_agent="climate_intel_v2_streamlit_app")
        
        try:
            # Added 10s timeout to prevent GeocoderUnavailable on slow networks
            location = geolocator.geocode(city_input, timeout=10)
        except GeocoderUnavailable:
            st.error("🌍 The geocoding service is temporarily busy. Please wait 10 seconds and try again.")
            st.stop()

        if location:
            # B. Execute Earth Engine Analysis
            # This calls the 'Titanium-Grade' engine.py we built
            aoi, current_lst, forecast_2030, stats, thumb_url = get_gee_data(
                city_input, 
                location.longitude, 
                location.latitude
            )
            
            if aoi and stats:
                # C. Display Interactive Map
                with col_map:
                    st.subheader(f"📍 Surface Temperature: {city_input}")
                    
                    # Initialize Map
                    m = lm.Map(center=[location.latitude, location.longitude], zoom=12)
                    
                    # Detailed thermal palette
                    vis_params = {
                        'min': 80, 
                        'max': 115, 
                        'palette': ['313695', '4575b4', 'abd9e9', 'ffffbf', 'fee090', 'f46d43', 'd73027', 'a50026']
                    }
                    
                    # Add Earth Engine Layers
                    m.add_ee_layer(current_lst, vis_params, 'Current Heat (2025)')
                    m.add_ee_layer(forecast_2030, vis_params, '2030 Projection')
                    
                    m.add_layer_control()
                    m.to_streamlit(height=650)
                
                # D. Display Gemini AI Insights
                with col_ai:
                    st.subheader("🤖 AI Climate Strategist")
                    
                    # Generate the AI report using stats and the satellite thumbnail
                    report = ask_gemini(
                        st.session_state.gemini_client, 
                        city_input, 
                        stats, 
                        thumb_url
                    )
                    
                    st.markdown(report)
                    
                    # Metrics Dashboard
                    st.divider()
                    m1, m2 = st.columns(2)
                    m1.metric("Mean Temp", f"{stats['mean_temp_f']}°F")
                    m2.metric("Max Hotspot", f"{stats['max_hotspot_f']}°F")
                    
                    st.caption(f"Warming Trend: {stats['warming_trend']}°F / year")
            else:
                # This triggers if engine.py returned None due to empty satellite data
                st.warning("Analysis could not be completed for this specific location.")
        else:
            st.error("Location not found. Please try a more specific address (e.g., 'Phoenix, Arizona').")
            
else:
    with col_map:
        st.info("👈 Enter a location in the sidebar to begin.")
        st.image("https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1200", 
                 caption="Satellite-driven Climate Intelligence")
