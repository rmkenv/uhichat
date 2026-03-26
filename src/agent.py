from google.genai import types

def ask_gemini(client, city, stats, thumb_url):
    system_prompt = f"""
    You are a Climate Risk Analyst. 
    Location: {city}
    Current Mean LST: {stats['mean_2024']:.1f}°F
    Annual Warming Trend: {stats['warming_rate']:.3f}°F/year
    
    Based on the satellite image provided (Blue=Cool, Red=Hot), explain the 2030 heat risk.
    If the trend is > 0.1°F/year, suggest urgent green infrastructure.
    """
    
    response = client.models.generate_content(
        model="gemini-3-flash",
        contents=[
            system_prompt,
            types.Part.from_uri(file_uri=thumb_url, mime_type="image/png")
        ]
    )
    return response.text
