import requests
from datetime import datetime, timedelta

API_KEY = "***REMOVED-EXPOSED-API-KEY***"
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


def get_weather(city="Lagos"):
    params = {"q": city, "appid": API_KEY, "units": "metric"}

    response = requests.get(BASE_URL, params=params)
    data = response.json()

    if response.status_code != 200:
        return "Sorry, I couldn't retrieve the weather."

    temperature = data["main"]["temp"]
    description = data["weather"][0]["description"]

    return f"The current temperature in {city} is {temperature} degrees Celsius with {description}."


def get_weather_forecast(city="Lagos", days_ahead=1):
    """Get weather forecast for a future date. days_ahead=1 is tomorrow, max 5."""
    if days_ahead <= 0:
        return get_weather(city)
    days_ahead = min(days_ahead, 5)

    params = {"q": city, "appid": API_KEY, "units": "metric", "cnt": 40}
    response = requests.get(FORECAST_URL, params=params)
    data = response.json()

    if response.status_code != 200:
        return "Sorry, I couldn't retrieve the weather forecast."

    target_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    day_name = (datetime.now() + timedelta(days=days_ahead)).strftime("%A")
    day_forecasts = [f for f in data["list"] if f["dt_txt"].startswith(target_date)]

    if not day_forecasts:
        return f"No forecast data available for {day_name}."

    noon_forecast = next(
        (f for f in day_forecasts if "12:00:00" in f["dt_txt"]),
        day_forecasts[0],
    )

    temp = noon_forecast["main"]["temp"]
    temp_min = min(f["main"]["temp_min"] for f in day_forecasts)
    temp_max = max(f["main"]["temp_max"] for f in day_forecasts)
    description = noon_forecast["weather"][0]["description"]
    humidity = noon_forecast["main"]["humidity"]
    wind_speed = noon_forecast["wind"]["speed"]
    rain_chance = int(max(f.get("pop", 0) for f in day_forecasts) * 100)

    return (
        f"On {day_name} in {city}: {description}. "
        f"High {temp_max:.0f}C, low {temp_min:.0f}C, around {temp:.0f}C midday. "
        f"Humidity {humidity}%, wind {wind_speed:.0f} m/s, rain chance {rain_chance}%."
    )
