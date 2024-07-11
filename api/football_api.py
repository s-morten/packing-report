import os
import http.client

api_key = os.environ['FOOTBALL_API_KEY']

conn = http.client.HTTPSConnection("v3.football.api-sports.io")

headers = {
    'x-rapidapi-host': "v3.football.api-sports.io",
    'x-rapidapi-key': api_key
    }

conn.request("GET", "/leagues", headers=headers)

res = conn.getresponse()
data = res.read()

print(data.decode("utf-8"))
