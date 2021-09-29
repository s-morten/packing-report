import requests
import pandas as pd
import numpy as np
# Danish Superliga id: 271
# Scottish Prem id: 501

API_TOKEN = "aQZHSwB6tywsjsL935mqke9oioIjaur7a62fbgKs9cbnNWJj0YHALfBLU2zf"

db = np.zeros(shape=(36,8))

request = f"https://soccer.sportmonks.com/api/v2.0/fixtures/16773956?api_token={API_TOKEN}&include=lineup,substitutions,corners"
r = requests.get(request)
data = r.json()

# TODO is Home or Away!

for idx, player in enumerate(data["data"]["lineup"]["data"]):
    db[idx][0] = player["player_id"]

for player in data["data"]["substitutions"]["data"]:
    idx = (db==0).argmax(axis=0)
    db[idx[0]][0] = player["player_in_id"]
    db[idx[0]][4] = (90 - player["minute"])
    idx = np.where(db == player["player_out_id"])
    db[idx[0][0]][4] = player["minute"]


    
np.set_printoptions(suppress=True)
print(db)