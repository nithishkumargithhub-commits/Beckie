import urllib
import urllib.request
import urllib.parse
import json
import logging

logger = logging.getLogger("VoiceAssistant.Weather")

# WMO Weather interpretation codes (WMO)
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail"
}

def get_weather(city_name: str) -> str:
    city_name = city_name.strip()
    if not city_name:
        return "Please tell me the name of the city."
        
    logger.info(f"Fetching weather for city: {city_name}")
    
    # 1. Geocoding API to get coordinates
    encoded_city = urllib.parse.quote(city_name)
    geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_city}&count=1&language=en&format=json"
    
    try:
        req = urllib.request.Request(geocode_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as response:
            geo_data = json.loads(response.read().decode())
            
        results = geo_data.get("results")
        if not results:
            return f"I couldn't find any location named '{city_name}'."
            
        loc = results[0]
        lat = loc["latitude"]
        lon = loc["longitude"]
        display_name = f"{loc.get('name')}, {loc.get('country')}"
        
        # 2. Weather forecast API using coordinates
        forecast_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m"
        
        req_forecast = urllib.request.Request(forecast_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_forecast, timeout=8) as response:
            weather_data = json.loads(response.read().decode())
            
        current = weather_data.get("current", {})
        temp = current.get("temperature_2m", "unknown")
        feels_like = current.get("apparent_temperature", "unknown")
        code = current.get("weather_code", 0)
        humidity = current.get("relative_humidity_2m", "unknown")
        wind_speed = current.get("wind_speed_10m", "unknown")
        
        condition = WEATHER_CODES.get(code, "unknown conditions")
        
        msg = (
            f"The current weather in {display_name} is {condition}. "
            f"The temperature is {temp} degrees Celsius, which feels like {feels_like} degrees. "
            f"Humidity is at {humidity} percent, and wind speed is {wind_speed} kilometers per hour."
        )
        return msg
        
    except urllib.error.URLError as e:
        logger.warning(f"Network error during weather fetch: {e}")
        return "I cannot check the weather because I am currently offline."
    except Exception as e:
        logger.error(f"Error during weather fetch: {e}")
        return "Sorry, I encountered an error while fetching the weather information."
