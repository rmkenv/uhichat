import streamlit as st
import ee
import geemap  # Change from 'import geemap.foliumap as geemap'
from google.genai import client
from src.engine import get_gee_data, initialize_ee
from src.agent import ask_gemini

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Gemini Climate Intelligence",
    page_icon="🌍",
    layout="wide"
)

st.title("🌍 Gemini 3 Flash: Climate Intelligence Agent")
st.markdown("""
    This agent uses **22 years of MODIS satellite data** and **Landsat 8/9 high-res imagery** to analyze urban heat islands and forecast 2030 climate risks.
""")

# --- 2. AUTHENTICATION & INITIALIZATION ---
# Initialize Earth Engine using the Service Account logic in engine.py
initialize_ee()

# Initialize Gemini Client
if "gemini_client" not in st.session_state:
    st.session_state.gemini_client = client.Client(api_key=st.secrets["GEMINI_API_KEY"])

# --- 3. SIDEBAR CONTROLS ---
st.sidebar.header("Target Analysis")
city_input = st.sidebar.text_input("City Name", "Atlanta, GA")
run_analysis = st.sidebar.button("Generate Intelligence Report", type="primary")

st.sidebar.divider()
st.sidebar.info("""
**How it works:**
1. **MODIS** calculates the 20-year warming slope.
2. **Landsat** provides 30m resolution detail.
3. **Gemini** performs multimodal reasoning on the resulting heatmap.
""")

# --- 4. MAIN DASHBOARD LAYOUT ---
col_map, col_ai = st.columns([2, 1])

if run_analysis:
    with st.spinner(f"🛰️ Accessing satellite constellations for {city_input}..."):
        try:
            # Call the GEE Engine
            aoi, current_img, forecast_img, stats, thumb_url = get_gee_data(city_input)
            
            # --- LEFT COLUMN: INTERACTIVE MAP ---
            with col_map:
                st.subheader("High-Resolution Surface Temperature (2024)")
                
                # Create the interactive map
                m = geemap.Map()
                m.centerObject(aoi, 12)
                
                vis_params = {
                    'min': 80, 
                    'max': 115, 
                    'palette': ['blue', 'yellow', 'red']
                }
                
                m.addLayer(current_img, vis_params, 'Current Heat Map (30m)')
                m.addLayer(forecast_2030, vis_params, '2030 Forecast (Predicted)', False)
                
                # Display the map in Streamlit
                m.to_streamlit(height=600)
                
                st.caption("Data source: USGS/NASA Landsat 8/9 & MODIS Aqua.")

            # --- RIGHT COLUMN: AI AGENT INSIGHTS ---
            with col_ai:
                st.subheader("🤖 AI Agent Analysis")
                
                # Send the data to Gemini for reasoning
                with st.chat_message("assistant"):
                    report = ask_gemini(
                        st.session_state.gemini_client, 
                        city_input, 
                        stats, 
                        thumb_url
                    )
                    st.write(report)
                
                # Add Key Metrics Cards
                st.divider()
                m1, m2 = st.columns(2)
                m1.metric("Avg Summer Temp", f"{stats['mean_2024']:.1f}°F")
                m2.metric("Warming Trend", f"+{stats['warming_rate']:.3f}°F/yr")
                
                # Add a download button for the report
                st.download_button(
                    label="💾 Download Report",
                    data=report,
                    file_name=f"{city_input}_climate_report.txt",
                    mime="text/plain"
                )

        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")
            st.info("Check if the city name is valid or if the Service Account has GEE access.")

else:
    with col_map:
        st.info("👈 Enter a city in the sidebar and click 'Run' to begin.")
    with col_ai:
        st.empty()
