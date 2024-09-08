import requests

def get_weather(url):
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response
        