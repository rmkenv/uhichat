import streamlit as st
import ee
import geemap.foliumap as geemap
from google import genai
from src.engine import get_gee_data
from src.agent import ask_gemini

st.set_page_config(page_title="Climate Agent", layout="wide")

# API Setup
PROJECT_ID = st.secrets["GCP_PROJECT_ID"]
GEMINI_KEY = st.secrets["GEMINI_API_KEY"]

if 'ee_init' not in st.session_state:
    ee.Initialize(project=PROJECT_ID)
    st.session_state.ee_init = True

client = genai.Client(api_key=GEMINI_KEY)

# UI Sidebar
st.sidebar.header("Settings")
city = st.sidebar.text_input("Analyze City", "Atlanta, GA")
run = st.sidebar.button("Run Intelligence Report")

# Main Layout
col1, col2 = st.columns([2, 1])

if run:
    with st.spinner("Analyzing Satellite Imagery..."):
        aoi, current, forecast, stats, thumb = get_gee_data(city)
        
        with col1:
            m = geemap.Map()
            m.centerObject(aoi, 12)
            m.addLayer(current, {'min': 85, 'max': 115, 'palette': ['blue', 'yellow', 'red']}, '2024 Heat')
            m.to_streamlit(height=600)
            
        with col2:
            st.subheader("🤖 AI Insights")
            report = ask_gemini(client, city, stats, thumb)
            st.write(report)
            st.metric("Trend Score", f"{stats['warming_rate']:.3f} °F/yr")
