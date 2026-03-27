import google.generativeai as genai
import streamlit as st

def get_chatbot_response(user_query, city_stats):
    """
    Feeds GEE satellite stats into Gemini 1.5 Flash for data-grounded reasoning.
    """
    try:
        # 1. Setup API
        api_key = st.secrets.get("GOOGLE_API_KEY")
        if not api_key:
            return "AI Error: GOOGLE_API_KEY not found in Streamlit Secrets."
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # 2. Create the Data Context (Grounding)
        # This prevents the AI from hallucinating and forces it to use YOUR data.
        context = f"""
        You are the 'Gemini Climate Intelligence Agent'. 
        You are analyzing real-time satellite data for {city_stats['city']}.
        
        DATA FROM GOOGLE EARTH ENGINE:
        - Current Baseline Surface Temp: {city_stats['mean_temp_f']}°F
        - 22-Year Warming Trend: {city_stats['warming_trend']}°F per year
        - 2026 Predictive Forecast: {city_stats['pred_2026_f']}°F
        
        INSTRUCTIONS:
        1. Use the data above to answer the user's question.
        2. If the warming trend is high (>0.05), suggest urban cooling strategies (green roofs, white pavement).
        3. Be professional, scientific, but accessible.
        4. Mention that the data comes from Landsat 8/9 and MODIS sensors.
        """
        
        # 3. Generate Response
        response = model.generate_content([context, user_query])
        return response.text
        
    except Exception as e:
        return f"I encountered an error analyzing the data: {str(e)}"
