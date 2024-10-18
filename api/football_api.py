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
        self.conn.request("GET", f'/fixtures?league={league_id}&season={season}&timezone=Europe/Berlin', headers=self.headers)
        res = self.conn.getresponse()
        data = res.read()

        return json.loads(data.decode("utf-8"))
    
    def get_formation(self, game_id):
        self.conn.request("GET", f"/fixtures/lineups?fixture={game_id}", headers=self.headers)

        res = self.conn.getresponse()
        data = res.read()

        return json.loads(data.decode("utf-8"))
    
    def get_odds(self, season, game_id, league):
        # bet 1 = match winner
        # bookmaker 8 = bet365
        self.conn.request("GET", f"/odds?season={season}&bet=1&bookmaker=8&fixture={game_id}&league={league}", headers=self.headers)
        res = self.conn.getresponse()
        data = res.read()

        return json.loads(data.decode("utf-8"))
        # {"get":"odds","parameters":{"season":"2024","bet":"1","bookmaker":"8","fixture":"1226178","league":"79"},"errors":[],"results":1,"paging":{"current":1,"total":1},"response":[{"league":{"id":79,"name":"2. Bundesliga","country":"Germany","logo":"https:\/\/media.api-sports.io\/football\/leagues\/79.png","flag":"https:\/\/media.api-sports.io\/flags\/de.svg","season":2024},"fixture":{"id":1226178,"timezone":"UTC","date":"2024-08-10T11:00:00+00:00","timestamp":1723287600},"update":"2024-08-08T18:28:42+00:00","bookmakers":[{"id":8,"name":"Bet365","bets":[{"id":1,"name":"Match Winner","values":[{"value":"Home","odd":"3.10"},{"value":"Draw","odd":"3.40"},{"value":"Away","odd":"2.25"}]}]}]}]}
