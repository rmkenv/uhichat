import streamlit as st
import leafmap.foliumap as lm
from geopy.geocoders import Nominatim
from google.genai import client
import os

# Import your custom logic
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

# 2. Initialize Core Services
initialize_ee()

if "gemini_client" not in st.session_state:
    # Ensure your GEMINI_API_KEY is set in Streamlit Secrets
    st.session_state.gemini_client = client.Client(api_key=st.secrets["GEMINI_API_KEY"])

# 3. Sidebar Navigation & Inputs
with st.sidebar:
    st.header("🔍 Analysis Settings")
    city_input = st.text_input("Enter City & State", "Phoenix, AZ")
    
    st.info("""
    This agent analyzes:
    * 20+ years of MODIS thermal trends.
    * 30m high-res Landsat 8/9 data.
    * 2030 heat island projections.
    """)
    
    run_analysis = st.button("Generate Intelligence Report", type="primary")

# 4. Main Interface Layout
col_map, col_ai = st.columns([1.5, 1])

if run_analysis:
    with st.spinner(f"🛰️ Accessing orbital data for {city_input}..."):
        # A. Geocode text to Coordinates
        geolocator = Nominatim(user_agent="climate_intel_v1")
        location = geolocator.geocode(city_input)
        
        if location:
            # B. Execute Earth Engine Analysis
            aoi, current_lst, forecast_2030, stats, thumb_url = get_gee_data(
                city_input, 
                location.longitude, 
                location.latitude
            )
            
            if aoi:
                # C. Display Interactive Map
                with col_map:
                    st.subheader(f"📍 Surface Temperature: {city_input}")
                    
                    # Create Map with leafmap
                    m = lm.Map(center=[location.latitude, location.longitude], zoom=12)
                    
                    vis_params = {
                        'min': 80, 
                        'max': 115, 
                        'palette': ['313695', '4575b4', 'abd9e9', 'ffffbf', 'fee090', 'f46d43', 'd73027', 'a50026']
                    }
                    
                    # Add Earth Engine Layers
                    m.add_ee_layer(current_lst, vis_params, 'Current Heat (2025)')
                    m.add_ee_layer(forecast_2030, vis_params, '2030 Projection')
                    
                    # Layer Control & Display
                    m.add_layer_control()
                    m.to_streamlit(height=650)
                
                # D. Display Gemini AI Insights
                with col_ai:
                    st.subheader("🤖 AI Climate Strategist")
                    
                    # Call Gemini with the thermal stats and the satellite thumbnail
                    report = ask_gemini(
                        st.session_state.gemini_client, 
                        city_input, 
                        stats, 
                        thumb_url
                    )
                    
                    st.markdown(report)
                    
                    # Quick Stats Cards
                    st.divider()
                    st_col1, st_col2 = st.columns(2)
                    with st_col1:
                        st.metric("Mean Temp", f"{stats['mean_temp_f']:.1f}°F")
                    with st_col2:
                        st.metric("Max Hotspot", f"{stats['max_hotspot_f']:.1f}°F")
                    
                    st.caption(f"Warming Trend: +{stats['warming_trend_f_per_year']:.3f}°F / year")
        else:
            st.error("Location not found. Please try a more specific address (City, State, Country).")
            
else:
    with col_map:
        st.info("👈 Use the sidebar to enter a location and begin the climate analysis.")
        # Optional: Show a placeholder image or global map here
        st.image("https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1200", 
                 caption="Satellite-driven Climate Intelligence")
