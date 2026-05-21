import requests

API_KEY = "***REMOVED-EXPOSED-API-KEY***"
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


def get_weather(city="Lagos"):
    params = {"q": city, "appid": API_KEY, "units": "metric"}

    response = requests.get(BASE_URL, params=params)
    data = response.json()

    if response.status_code != 200:
        return "Sorry, I couldn't retrieve the weather."

    temperature = data["main"]["temp"]
    description = data["weather"][0]["description"]

    return f"The current temperature in {city} is {temperature} degrees Celsius with {description}."
