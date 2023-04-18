import requests
import json
import sqlite3
import time
from datetime import datetime

# Danish Superliga id: 271
# Scottish Prem id: 501

API_TOKEN = json.load(open('/home/morten/Develop/secrets.json', 'r'))['sportmonks']['API_TOKEN']
Danish_SL = 271
Scottish_Prem = 501

request = f"https://soccer.sportmonks.com/api/v2.0/seasons?api_token={API_TOKEN}&league={Danish_SL}"
# request = f"https://soccer.sportmonks.com/api/v2.0/fixtures/date/2020-08-02?api_token={API_TOKEN}&leagues=271"
r = requests.get(request)
print(r)
data = r.json()
league_list = []
for x in data["data"]:
    league_list.append(x["id"])

print(
    f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} Number of Leagues: {len(league_list)}"
)

game_list = []
for season in league_list:
    request = f"https://soccer.sportmonks.com/api/v2.0/rounds/season/{season}?api_token={API_TOKEN}&include=fixtures"

    r = requests.get(request)
    data = r.json()
    for gameday in data["data"]:
        for game in gameday["fixtures"]["data"]:
            # print(f"{gameday['name']}, {game['id']}, {game['localteam_id']}, {game['visitorteam_id']}" )
            game_list.append(game["id"])

print(
    f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} Number of Games: {len(game_list)}"
)
time.sleep(7200)

while game_list:

    num_requests = 170
    if len(game_list) > num_requests:
        game_sub_list = game_list[:num_requests]
        game_list = game_list[num_requests:]

        print(
            f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} Number of new Requests: {len(game_sub_list)}"
        )
        print(
            f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} Number of Requests left: {len(game_list)}"
        )

    else:
        game_sub_list = game_list
        print(
            f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} Number of new Requests: {len(game_sub_list)}"
        )

    for game in game_sub_list:
        request = f"https://soccer.sportmonks.com/api/v2.0/fixtures/{game}?api_token={API_TOKEN}&include=lineup,substitutions,events,corners"

        r = requests.get(request)

        data = r.json()

        # print(json.dumps(data, indent=2))
        if data["data"]["lineup"]["data"]:
            print(
                f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} Lineup is empty: skip {game}"
            )
            continue
        if data["data"]["corners"]["data"]:
            print(
                f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} Corners is empty: skip {game}"
            )
            continue

        con = sqlite3.connect("cI.db")

        cur = con.cursor()

        # for each match
        localTeam = data["data"]["localteam_id"]
        visitorTeam = data["data"]["visitorteam_id"]
        # date to string
        date = data["data"]["time"]["starting_at"]["date"]
        date = date.split("-")
        date = date[0] + date[1] + date[2]
        # add corners!
        for x in data["data"]["corners"]["data"]:
            if x["comment"][0] == "R":
                continue  # skip "Race to Nth Corner events"
            team_id = x["team_id"]
            corner_min = x["minute"]
            cur.execute(
                f"INSERT INTO game (game_id, corner_min, team_id, date) VALUES ({game},{corner_min},{team_id},{date})"
            )
            print(
                f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} Added Corners to Game: {game}"
            )

        for x in data["data"]["lineup"]["data"]:
            player_id = x["player_id"]
            home = 0 if x["team_id"] == str(localTeam) else 1
            min_on = 0
            min_off = x["stats"]["other"]["minutes_played"]
            cur.execute(
                f"INSERT INTO lineup (game_id, player_id, home, min_on, min_off, team_id) VALUES ({game},{player_id},{home},{min_on},{min_off},{x['team_id']})"
            )
            print(
                f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} Added Lineup for Game: {game}"
            )

        for x in data["data"]["substitutions"]["data"]:
            player_id = x["player_in_id"]
            home = 0 if x["team_id"] == localTeam else 1
            min_on = x["minute"]
            min_off = 90
            cur.execute(
                f"INSERT INTO lineup (game_id, player_id, home, min_on, min_off, team_id) VALUES ({game},{player_id},{home},{min_on},{min_off},{x['team_id']})"
            )
            print(
                f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} Added Subs for Game: {game}"
            )

        con.commit()

    time.sleep(7200)
