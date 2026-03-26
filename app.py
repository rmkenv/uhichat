import streamlit as st
import geemap.foliumap as geemap
from geopy.geocoders import Nominatim
from google.genai import client
from src.engine import get_gee_data, initialize_ee
from src.agent import ask_gemini

st.set_page_config(page_title="Climate Intelligence", layout="wide")
st.title("🌍 Gemini Climate Intelligence Agent")

# Initialize GEE and Gemini
initialize_ee()
if "gemini_client" not in st.session_state:
    st.session_state.gemini_client = client.Client(api_key=st.secrets["GEMINI_API_KEY"])

# Sidebar
st.sidebar.header("Analysis Settings")
city_input = st.sidebar.text_input("Enter City Name", "Atlanta, GA")
run_analysis = st.sidebar.button("Run Intelligence Report", type="primary")

col_map, col_ai = st.columns([2, 1])

if run_analysis:
    with st.spinner("🌍 Locating city and fetching satellite data..."):
        # 1. Geocode text to Lat/Lon
        geolocator = Nominatim(user_agent="climate_app_2026")
        location = geolocator.geocode(city_input)
        
        if location:
            # 2. Call Engine with coordinates
            aoi, current_lst, forecast_2030, stats, thumb_url = get_gee_data(
                city_input, location.longitude, location.latitude
            )
            
            if aoi:
                with col_map:
                    st.subheader(f"Surface Temperature: {city_input}")
                    m = geemap.Map()
                    m.centerObject(aoi, 12)
                    vis = {'min': 80, 'max': 115, 'palette': ['blue', 'yellow', 'red']}
                    m.addLayer(current_lst, vis, 'Current Heat (2025)')
                    m.addLayer(forecast_2030, vis, '2030 Forecast', False)
                    m.to_streamlit(height=600)
                
                with col_ai:
                    st.subheader("🤖 Gemini Analysis")
                    report = ask_gemini(st.session_state.gemini_client, city_input, stats, thumb_url)
                    st.write(report)
                    
                    st.metric("Avg Summer Temp", f"{stats['mean_temp_f']:.1f}°F")
                    st.metric("Warming Rate", f"+{stats['warming_trend']:.3f}°F/year")
        else:
            st.error("Could not find that location. Try adding a state or country.")
else:
    with col_map:
        st.info("👈 Enter a city to begin analysis.")
