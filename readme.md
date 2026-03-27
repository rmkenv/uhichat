
# 🌍 Gemini Climate Intelligence Agent (v2026)

An AI-native geospatial application that combines **Google Earth Engine (GEE)** satellite analytics with multi-decadal climate modeling to forecast urban heat risks for the top 25 most populated US cities.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_svg.svg)](https://uhichat.streamlit.app/)

---

## 🚀 Overview
This agent doesn't just show a map; it **reasons** over 22 years of climate data to identify specific neighborhood-level vulnerabilities and thermal trajectories.

- **Satellite Engine:** Processes **MODIS (2003–2026)** to calculate a robust warming trend using **Sen's Slope** and **Landsat 8/9** for high-resolution 30m surface temperature mapping.
- **Predictive Analytics:** Projects 2026 thermal baselines by merging historical multi-decadal trends with current median surface temperatures.
- **Interactive UI:** A high-performance Streamlit dashboard featuring dynamic opacity toggles, interactive color ramps, and server-side GEE tile injection for seamless performance.

---

## 🛠️ Tech Stack
- **Language:** Python 3.11+
- **Frontend:** [Streamlit](https://streamlit.io/)
- **Geospatial:** [Google Earth Engine](https://earthengine.google.com/) (Service Account Auth)
- **Mapping:** [Leafmap](https://leafmap.org/) / Folium
- **Data Sources:** NASA/USGS Landsat Collection 2 Level 2 & MODIS MYD11A2.061

---

## 📂 Repository Structure
```text
├── .streamlit/          # Streamlit Secrets (GEE Credentials)
├── src/
│   ├── __init__.py      # Package identifier (Critical for Cloud Import)
│   └── engine.py        # GEE Logic: Sen's Slope & Tile Generation
├── app.py               # Main Entry Point (UI, Sliders, & Mapping)
├── requirements.txt     # Dependencies (earthengine-api, leafmap)
└── README.md            # Documentation
```

---

## 🌐 Live Access
Explore the interactive heat maps and 2026 forecasts here:
**👉 [https://uhichat.streamlit.app/](https://uhichat.streamlit.app/)**

---

## 🧪 Methodology
1. **Historical Trend:** We extract 22 years of MODIS daytime Land Surface Temperature (LST) to calculate the "Warming Trend" ($^\circ\text{F/year}$) using a robust linear regression.

2. **Current Detail:** We utilize Landsat 8/9 thermal bands (TIRS) to create a 30m resolution "Current Baseline," allowing for street-level heat island detection.
3. **The 2026 Forecast:** The projection is calculated by applying the localized historical slope to the high-resolution baseline:
   $$\text{Forecast}_{2026} = \text{Landsat}_{\text{Median}} + (\text{Sen's Slope} \times 2)$$
4. **Visualization:** Data is pre-visualized on the GEE server-side using a fixed color ramp (85°F to 115°F) to ensure consistent visual analysis across different geographic regions.


---

## ⚠️ Known Issues & Quotas
- **Cloud Masking:** While the engine filters for <40% cloud cover, some artifacts may appear in high-humidity coastal regions (e.g., NYC or Miami).
- **GEE Quotas:** If the map fails to load, the service account may have hit its concurrent request limit. Refreshing usually resolves this.

---

**Developed for the [uhichat](https://github.com/rmkenv/uhichat) project.**
```

