# 🌍 Gemini Climate Intelligence Agent (v2026)

An AI-native geospatial application that combines **Google Earth Engine (GEE)** satellite analytics with **Gemini 3 Flash** multimodal reasoning to forecast urban heat risks.

---

## 🚀 Overview
This agent doesn't just show a map; it **reasons** over 22 years of climate data. 
- **Satellite Engine:** Uses MODIS (2003–2024) to calculate a robust warming trend (Sen's Slope) and Landsat 8/9 for 30m neighborhood detail.
- **AI Orchestrator:** Gemini 3 Flash analyzes the visual heat distribution and numerical stats to provide 2030 forecasts and urban planning recommendations.
- **Interactive UI:** Built with Streamlit and Geemap for real-time city-wide exploration.

---

## 🛠️ Tech Stack
- **Language:** Python 3.10+
- **Frontend:** [Streamlit](https://streamlit.io/)
- **Geospatial:** [Google Earth Engine](https://earthengine.google.com/)
- **LLM:** [Gemini 3 Flash](https://aistudio.google.com/) (via Google GenAI SDK)
- **Mapping:** [Geemap](https://geemap.org/)

---

## 📂 Repository Structure
```text
├── .streamlit/          # Configuration & Secrets
├── src/
│   ├── engine.py        # GEE Satellite Logic (Landsat/MODIS)
│   └── agent.py         # Gemini Prompting & Reasoning
├── app.py               # Main Entry Point (Streamlit UI)
├── requirements.txt     # Dependencies
└── .gitignore           # Exclusions (Secrets/Cache)
