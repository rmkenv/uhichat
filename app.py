import streamlit as st
import leafmap.foliumap as lm
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderRateLimited, GeocoderServiceError
from google.genai import client
import time
import random

# Internal logic imports
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

# 2. Initialize Earth Engine (Handles Auth & Scopes)
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
    with st.spinner(f"📡 Requesting orbital data for {city_input}..."):
        
        # --- FIX: Rate-Limit Proof Geocoding ---
        # We use a random ID in the user_agent to avoid 429 errors 
        # shared by other apps on the same Streamlit Cloud IP.
        random_id = random.randint(1000, 9999)
        geolocator = Nominatim(user_agent=f"climate_agent_{random_id}")
        
        # The RateLimiter adds a 2-second buffer and 3 retries 
        # to satisfy the free Nominatim usage policy.
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=2, max_retries=3)
        
        try:
            location = geocode(city_input)
        except (GeocoderRateLimited, GeocoderServiceError):
            st.error("🌍 The mapping service is overloaded (Error 429). Please wait 10 seconds and try again.")
            st.stop()

        if location:
            # B. Execute Earth Engine Analysis (from engine.py)
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
                    
                    # Call Gemini with the thermal stats and the satellite thumbnail
                    report = ask_gemini(
                        st.session_state.gemini_client, 
                        city_input, 
                        stats, 
                        thumb_url
                    )
                    
                    st.markdown(report)
                    
                    # Dashboard Metrics
                    st.divider()
                    m1, m2 = st.columns(2)
                    m1.metric("Mean Temp", f"{stats['mean_temp_f']:.1f}°F")
                    m2.metric("Max Hotspot", f"{stats['max_hotspot_f']:.1f}°F")
                    
                    st.caption(f"Warming Trend: {stats['warming_trend']:.4f}°F / year")
            else:
                st.warning("Satellite data is currently unavailable for this specific coordinate.")
        else:
            st.error("Location not found. Please try a more specific address.")
            
else:
    with col_map:
        st.info("👈 Enter a location in the sidebar to begin the satellite analysis.")
        st.image("https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1200", 
                 caption="Satellite-driven Climate Intelligence")
