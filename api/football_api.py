import os
import http.client
import json

class FApi_Handler:
    def __init__(self):
        self.api_key = os.environ['FOOTBALL_API_KEY']

        self.conn = http.client.HTTPSConnection("v3.football.api-sports.io")

        self.headers = {
            'x-rapidapi-host': "v3.football.api-sports.io",
            'x-rapidapi-key': self.api_key
            }
        
    def get_schedule(self, league_id, season):
        self.conn.request("GET", f'/fixtures?league={league_id}&season={season}', headers=self.headers)
        res = self.conn.getresponse()
        data = res.read()

        return json.loads(data.decode("utf-8"))
    
    def get_formation(self, game_id):
        self.conn.request("GET", f"/fixtures/lineups?fixture={game_id}", headers=headers)

        res = self.conn.getresponse()
        data = res.read()

        return json.loads(data.decode("utf-8"))