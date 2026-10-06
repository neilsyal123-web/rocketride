import requests

url = "https://official-joke-api.appspot.com/random_joke"

response = requests.get(url, timeout=10)
response.raise_for_status()

joke = response.json()
print(joke["setup"])
print(joke["punchline"])
