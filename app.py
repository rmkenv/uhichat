import streamlit as st
import leafmap.foliumap as leafmap
import os
import sys

# 1. DYNAMIC PATH FIX
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from src.engine import get_gee_data
from src.agent import get_chatbot_response

# 2. PAGE CONFIG
st.set_page_config(page_title="Urban Heat Agent 2026", layout="wide", page_icon="🔥")

# 3. SIDEBAR & CITY DATA
st.sidebar.title("🏙️ Heat Agent v6.0")
st.sidebar.markdown("[🔗 GitHub Repo](https://github.com/rmkenv/uhichat)")

CITIES = {
    "Atlanta, GA": {"lat": 33.7490, "lon": -84.3880},
    "New York, NY": {"lat": 40.7128, "lon": -74.0060},
    "Phoenix, AZ": {"lat": 33.4484, "lon": -112.0740},
    "Chicago, IL": {"lat": 41.8781, "lon": -87.6298},
    "Houston, TX": {"lat": 29.7604, "lon": -95.3698},
    "Los Angeles, CA": {"lat": 34.0522, "lon": -118.2437}
}

selected_city = st.sidebar.selectbox("Select Target City", sorted(list(CITIES.keys())))
coords = CITIES[selected_city]

st.sidebar.subheader("Map Opacity")
base_op = st.sidebar.slider("2024 Baseline", 0.0, 1.0, 0.6, 0.05)
pred_op = st.sidebar.slider("2026 Forecast", 0.0, 1.0, 0.7, 0.05)

# 4. SATELLITE ENGINE EXECUTION
with st.spinner(f"Fetching GEE tiles for {selected_city}..."):
    stats = get_gee_data(selected_city, coords["lon"], coords["lat"])

if stats:
    st.title(f"Thermal Analysis: {selected_city}")
    
    # METRICS
    m1, m2, m3 = st.columns(3)
    m1.metric("Baseline Temp", f"{stats['mean_temp_f']}°F")
    m2.metric("Warming Trend", f"{stats['warming_trend']}°F/yr")
    gain = round(stats['pred_2026_f'] - stats['mean_temp_f'], 2)
    m3.metric("2026 Forecast", f"{stats['pred_2026_f']}°F", delta=f"{gain}°F")

    # THE MAP
    m = leafmap.Map(center=[coords["lat"], coords["lon"]], zoom=11)
    m.add_basemap("SATELLITE")
    m.add_tile_layer(url=stats["current_url"], name="2024 Baseline", attribution="GEE", opacity=base_op)
    m.add_tile_layer(url=stats["forecast_url"], name="2026 Prediction", attribution="GEE", opacity=pred_op)
    m.add_colorbar(colors=['#0000ff', '#ffff00', '#ff0000'], vmin=85, vmax=115, label="Surface Temp (°F)")
    m.add_layer_control()
    
    map_key = f"map_{selected_city}_{base_op}_{pred_op}"
    m.to_streamlit(height=600, key=map_key)

    # 5. CHATBOT INTERFACE (The New Addition)
    st.markdown("---")
    st.subheader(f"💬 Chat with {selected_city} Climate Data")
    
    # Initialize chat session
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input
    if prompt := st.chat_input("Ex: 'What are the main heat risks here?'"):
        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get AI response
        with st.chat_message("assistant"):
            stats["city"] = selected_city # Add city name to stats dict for the AI
            response = get_chatbot_response(prompt, stats)
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

else:
    st.error("Engine failed to synchronize with Google Earth Engine.")
