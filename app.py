import streamlit as st
import leafmap.foliumap as lm
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderRateLimited, GeocoderServiceError
from google.genai import client
import random

# Internal logic imports
from src.engine import get_gee_data, initialize_ee
from src.agent import ask_gemini

# 1. Hard-coded Top 25 Cities (Latitude, Longitude)
# This prevents 429 errors and provides instant results for major hubs.
TOP_CITIES = {
    "New York, NY": (40.7128, -74.0060),
    "Los Angeles, CA": (34.0522, -118.2437),
    "Chicago, IL": (41.8781, -87.6298),
    "Houston, TX": (29.7604, -95.3698),
    "Phoenix, AZ": (33.4484, -112.0740),
    "Philadelphia, PA": (39.9526, -75.1652),
    "San Antonio, TX": (29.4241, -98.4936),
    "San Diego, CA": (32.7157, -117.1611),
    "Dallas, TX": (32.7767, -96.7970),
    "San Jose, CA": (37.3382, -121.8863),
    "Austin, TX": (30.2672, -97.7431),
    "Jacksonville, FL": (30.3322, -81.6557),
    "Fort Worth, TX": (32.7555, -97.3308),
    "Columbus, OH": (39.9612, -82.9988),
    "Charlotte, NC": (35.2271, -80.8431),
    "San Francisco, CA": (37.7749, -122.4194),
    "Indianapolis, IN": (39.7684, -86.1581),
    "Seattle, WA": (47.6062, -122.3321),
    "Denver, CO": (39.7392, -104.9903),
    "Washington, DC": (38.9072, -77.0369),
    "Boston, MA": (42.3601, -71.0589),
    "El Paso, TX": (31.7619, -106.4850),
    "Nashville, TN": (36.1627, -86.7816),
    "Detroit, MI": (42.3314, -83.0458),
    "Oklahoma City, OK": (35.4676, -97.5164)
}

# 2. Page Configuration
st.set_page_config(
    page_title="Climate Intelligence Agent",
    page_icon="🌍",
    layout="wide"
)

st.title("🌍 Gemini 3 Climate Intelligence")
st.markdown("---")

# 3. Initialize Services
initialize_ee()
if "gemini_client" not in st.session_state:
    st.session_state.gemini_client = client.Client(api_key=st.secrets["GEMINI_API_KEY"])

# 4. Sidebar UI
with st.sidebar:
    st.header("🔍 Analysis Settings")
    
    # Selection Mode
    city_choice = st.selectbox("Select a City", list(TOP_CITIES.keys()) + ["Search Other..."])
    
    # Conditional text input if "Search Other" is selected
    if city_choice == "Search Other...":
        target_city = st.text_input("Enter City, State/Country", "")
    else:
        target_city = city_choice
    
    st.info("""
    **Satellite Sources:**
    * MODIS (20-year Thermal Trends)
    * Landsat 8/9 (30m High-Res)
    * Gemini 3 (Predictive Analysis)
    """)
    
    run_analysis = st.button("Generate Intelligence Report", type="primary")

# 5. Main Layout
col_map, col_ai = st.columns([1.5, 1])

if run_analysis and target_city:
    with st.spinner(f"📡 Accessing orbital data for {target_city}..."):
        
        # --- HYBRID GEOLOCATION LOGIC ---
        location_coords = None
        
        if target_city in TOP_CITIES:
            # INSTANT LOOKUP (No API Call)
            lat, lon = TOP_CITIES[target_city]
            # Mock the geopy object structure
            location_coords = type('Location', (object,), {'latitude': lat, 'longitude': lon})
        else:
            # FALLBACK TO GEOPY (Rate-Limited API Call)
            try:
                unique_agent = f"climate_agent_rel_{random.randint(1000, 9999)}"
                geolocator = Nominatim(user_agent=unique_agent)
                # Ensure we don't spam OSM servers
                geocode_service = RateLimiter(geolocator.geocode, min_delay_seconds=1.5, max_retries=2)
                location_coords = geocode_service(target_city)
            except Exception:
                location_coords = None

        if location_coords:
            # B. Execute Earth Engine Analysis
            aoi, current_lst, forecast_2030, stats, thumb_url = get_gee_data(
                target_city, 
                location_coords.longitude, 
                location_coords.latitude
            )
            
            if aoi and stats:
                # C. Display Interactive Map
                with col_map:
                    st.subheader(f"📍 Surface Temperature: {target_city}")
                    m = lm.Map(center=[location_coords.latitude, location_coords.longitude], zoom=12)
                    
                    vis_params = {
                        'min': 80, 
                        'max': 115, 
                        'palette': ['313695', '4575b4', 'abd9e9', 'ffffbf', 'fee090', 'f46d43', 'd73027', 'a50026']
                    }
                    
                    m.add_ee_layer(current_lst, vis_params, 'Current Heat (2025)')
                    m.add_ee_layer(forecast_2030, vis_params, '2030 Projection')
                    m.add_layer_control()
                    m.to_streamlit(height=650)
                
                # D. Display Gemini AI Insights
                with col_ai:
                    st.subheader("🤖 AI Climate Strategist")
                    report = ask_gemini(
                        st.session_state.gemini_client, 
                        target_city, 
                        stats, 
                        thumb_url
                    )
                    st.markdown(report)
                    
                    st.divider()
                    m1, m2 = st.columns(2)
                    m1.metric("Mean Temp", f"{stats['mean_temp_f']:.1f}°F")
                    m2.metric("Max Hotspot", f"{stats['max_hotspot_f']:.1f}°F")
                    st.caption(f"Warming Trend: {stats['warming_trend']:.4f}°F / year")
            else:
                st.warning("Analysis could not be completed. Check for satellite coverage in this region.")
        else:
            st.error("Location not found. Please check your spelling or try a major city.")
            
else:
    with col_map:
        st.info("👈 Select a location in the sidebar to begin.")
        st.image("https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1200")
