import json
import os
import time
import requests
import time
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from difflib import SequenceMatcher
import twitterAPI as twitterAPI
from tinydb import TinyDB, Query

# An api key is emailed to you when you sign up to a plan
api_key = json.load(open("/home/morten/Develop/secrets.json", "r"))["odds-api"][
    "API_TOKEN"
]

db = TinyDB("./database/db.json")
Matches = Query()


def logPrint(text):
    print(datetime.now().strftime("%d/%m/%Y, %H:%M:%S") + "    " + text)


def getReverseOdds(inOdd):
    inputOdd = float(inOdd)
    rOdd = 100 / inputOdd
    return rOdd


def sendMail(subject, text):

    senderEmail = "mortensportwetten@gmail.com"
    empfangsEmail = "mortensportwetten@gmail.com"
    msg = MIMEMultipart()
    msg["From"] = senderEmail
    msg["To"] = empfangsEmail
    msg["Subject"] = subject

    emailText = text
    msg.attach(MIMEText(emailText, "html"))

    server = smtplib.SMTP("smtp.gmail.com", 587)  # Die Server Daten
    server.starttls()
    server.login(
        senderEmail,
        json.load(open("/home/morten/Develop/secrets.json", "r"))[
            "gmail-mortensportwetten"
        ]["password"],
    )  # Das Passwort
    text = msg.as_string()
    server.sendmail(senderEmail, empfangsEmail, text)
    server.quit()


def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()


def oddCalc(inputO):
    # inputOdd = 2.15346
    divisor = 1

    # inputOdd = input("Enter Odd: ")
    inputOdd = float(inputO)
    outputOdd = inputOdd

    while inputOdd % 1 != 0:
        inputOdd *= 10
        divisor *= 10

    multiplicator = inputOdd - divisor
    probability = divisor / (multiplicator + divisor)

    # for percentage
    probability *= 100

    # print("The Probability for " + str(outputOdd) + " is " + str(probability))
    return probability


def updateOddList():
    # To get odds for a sepcific sport, use the sport key from the last request
    #   or set sport to "upcoming" to see live and upcoming across all sports
    sport_key = "soccer"

    odds_response = requests.get(
        "https://api.the-odds-api.com/v3/odds",
        params={
            "api_key": api_key,
            "sport": sport_key,
            "region": "uk",  # uk | us | au
            "mkt": "h2h",  # h2h | spreads | totals
        },
    )
    odds_json = json.loads(odds_response.text)
    if not odds_json["success"]:
        print("There was a problem with the odds request:", odds_json["msg"])
        return False
    else:
        # odds_json['data'] contains a list of live and
        #   upcoming events and odds for different bookmakers.
        # Events are ordered by start time (live events are first)
        logPrint("Successfully got {} events".format(len(odds_json["data"])))
        # print(odds_json['data'][0])
        time_now = time.time()
        # print(time_now)
        with open("api.spwdata", "w") as f:
            for item in odds_json["data"]:
                if item["commence_time"] > (time_now - 7200):  # no live data
                    home_team = item["home_team"]
                    if item["teams"][0] == home_team:
                        switched = False
                        away_team = item["teams"][1]
                    else:
                        away_team = item["teams"][0]
                        switched = True

                    f.write(str(time_now) + "\n")
                    f.write(f"{home_team} vs. {away_team}\n")
                    for odd in item["sites"]:
                        if switched:
                            f.write(
                                f"{odd['site_key']}: {odd['odds']['h2h'][1]}-{odd['odds']['h2h'][2]}-{odd['odds']['h2h'][0]}\n"
                            )
                            f.write(
                                f"{odd['site_key']}: {oddCalc(odd['odds']['h2h'][1])}-{oddCalc(odd['odds']['h2h'][2])}-{oddCalc(odd['odds']['h2h'][0])}\n"
                            )
                        else:
                            f.write(
                                f"{odd['site_key']}: {odd['odds']['h2h'][0]}-{odd['odds']['h2h'][2]}-{odd['odds']['h2h'][1]}\n"
                            )
                            f.write(
                                f"{odd['site_key']}: {oddCalc(odd['odds']['h2h'][0])}-{oddCalc(odd['odds']['h2h'][2])}-{oddCalc(odd['odds']['h2h'][1])}\n"
                            )
                    f.write("---\n")

        logPrint(
            f"Remaining requests:  {odds_response.headers['x-requests-remaining']}"
        )
        db.update(
            {"RemainingRequests": odds_response.headers["x-requests-remaining"]},
            Matches.RemainingRequests,
        )
        # print('Used requests', odds_response.headers['x-requests-used'])
        return True


def getHighestIndex():
    index = 0
    for item in db:
        if int(item.get("BetIndex")) > index:
            index = int(item.get("BetIndex"))
    return index


def isAtInList(teamH, teamA, matchList=[]):
    teamH = teamH.split(" ")
    teamA = teamA.split(" ")
    # print(teamH)
    # print(teamA)
    for idx, item in enumerate(matchList):
        for idx2, teamHitem in enumerate(teamH):
            # print(teamHitem)
            for idx3, teamAitem in enumerate(teamA):
                matchListHome = item[0].split(" ")
                matchListAway = item[1].split(" ")
                # print(matchListHome)
                # print(matchListAway)
                for idx4, mlHitem in enumerate(matchListHome):
                    for idx5, mlAitem in enumerate(matchListAway):
                        # print(f"{idx2}{idx3}{idx4}{idx5}")
                        # print(f"{teamHitem}-{mlHitem}--{teamAitem}-{mlAitem}")
                        if (
                            len(teamHitem) >= 3
                            and len(teamAitem) >= 3
                            and len(mlHitem) >= 3
                            and len(mlAitem) >= 3
                        ):
                            if (similar(teamHitem, mlHitem) >= 0.8) and (
                                similar(teamAitem, mlAitem) >= 0.8
                            ):
                                return idx
    return -1


counter = 0
while True:
    if twitterAPI.run():
        try:
            updateOddList()
            with open("api.spwdata", "r") as o:
                # sendMail("Test")
                matches = []
                apiOdds = o.read()
                apiOdd = list(filter(None, apiOdds.split("---\n")))
                for allGameData in apiOdd:
                    lines = allGameData.split("\n")
                    game = lines[1].split(" vs. ")
                    matches.append([game[0], game[1]])

                allMatches = db.search(Matches.BetTaken == None)
                for matchThings in allMatches:
                    # print(len(matchThings))
                    betIndex = matchThings.get("BetIndex")
                    home = matchThings.get("Home")
                    away = matchThings.get("Away")

                    homewin = matchThings.get("GIHomeOdd")
                    draw = matchThings.get("GIDrawOdd")
                    awaywin = matchThings.get("GIAwayOdd")

                    # print(f"{home} vs. {away} Odds: {homewin}___{draw}___{awaywin}")
                    idx = isAtInList(home, away, matches)
                    print(idx)
                    if idx >= 0:
                        writtenHome = False
                        writtenDraw = False
                        writtenAway = False
                        sendMailHome = False
                        sendMailDraw = False
                        sendMailAway = False
                        logPrint(f"{home} and {away} are in List at index {idx}")
                        apiEntry = apiOdd[idx]
                        oddLines = apiEntry.split("\n")
                        for i, line in enumerate(oddLines):
                            if i >= 3 and ((i % 2) != 0):
                                odds = line.split(": ")
                                anbieter = odds[0]
                                odds = odds[1]
                                odds = odds.split("-")
                                homeOdd = odds[0]
                                drawOdd = odds[1]
                                awayOdd = odds[2]
                                if float(homewin) - float(homeOdd) >= 5:
                                    if not sendMailHome:
                                        logPrint(
                                            "Bookie Odds: "
                                            + str(homeOdd)
                                            + " "
                                            + str(drawOdd)
                                            + " "
                                            + str(awayOdd)
                                        )
                                        logPrint(
                                            f"Wette auf {home} bei {anbieter}, da GoalImpact Quote {float(homewin) - float(homeOdd)}% besser ist"
                                        )
                                        sendMail(
                                            f"{home} vs. {away}",
                                            f"Wette auf {home} bei {anbieter}, da GoalImpact Quote {float(homewin) - float(homeOdd)}% besser ist\n{getReverseOdds(homeOdd)}",
                                        )
                                        logPrint(
                                            "GI: "
                                            + str(homewin)
                                            + " "
                                            + str(draw)
                                            + " "
                                            + str(awaywin)
                                        )
                                        sendMailHome = True
                                    if not writtenHome:
                                        found = db.search(Matches.BetIndex == betIndex)
                                        if found[0].get("BetTaken") != None:
                                            db.insert(
                                                {
                                                    "BetIndex": getHighestIndex() + 1,
                                                    "BetTaken": True,
                                                    "Home": found[0].get("Home"),
                                                    "Away": found[0].get("Away"),
                                                    "GIHomeOdd": found[0].get(
                                                        "GIHomeOdd"
                                                    ),
                                                    "GIDrawOdd": found[0].get(
                                                        "GIDrawOdd"
                                                    ),
                                                    "GIAwayOdd": found[0].get(
                                                        "GIAwayOdd"
                                                    ),
                                                    "Bet": "Home",
                                                    "Odd": getReverseOdds(homeOdd),
                                                    "Better": float(homewin)
                                                    - float(homeOdd),
                                                    "Won": None,
                                                }
                                            )
                                        else:
                                            db.update(
                                                {
                                                    "BetTaken": True,
                                                    "Bet": "Home",
                                                    "Odd": getReverseOdds(homeOdd),
                                                    "Better": float(homewin)
                                                    - float(homeOdd),
                                                },
                                                Matches.BetIndex == betIndex,
                                            )
                                        writtenHome = True
                                if float(draw) - float(drawOdd) >= 5:
                                    if not sendMailDraw:
                                        logPrint(
                                            f"Wette auf Unentschieden bei {anbieter}, da GoalImpact Quote {float(draw) - float(drawOdd)}% besser ist"
                                        )
                                        logPrint(
                                            "Bookie Odds: "
                                            + str(homeOdd)
                                            + " "
                                            + str(drawOdd)
                                            + " "
                                            + str(awayOdd)
                                        )
                                        sendMail(
                                            f"{home} vs. {away}",
                                            f"Wette auf Unentschieden bei {anbieter}, da GoalImpact Quote {float(draw) - float(drawOdd)}% besser ist\n{getReverseOdds(drawOdd)}",
                                        )
                                        logPrint(
                                            "GI: "
                                            + str(homewin)
                                            + " "
                                            + str(draw)
                                            + " "
                                            + str(awaywin)
                                        )
                                        sendMailDraw = True
                                    if not writtenDraw:
                                        found = db.search(Matches.BetIndex == betIndex)
                                        if found[0].get("BetTaken") != None:
                                            db.insert(
                                                {
                                                    "BetIndex": getHighestIndex() + 1,
                                                    "BetTaken": True,
                                                    "Home": found[0].get("Home"),
                                                    "Away": found[0].get("Away"),
                                                    "GIHomeOdd": found[0].get(
                                                        "GIHomeOdd"
                                                    ),
                                                    "GIDrawOdd": found[0].get(
                                                        "GIDrawOdd"
                                                    ),
                                                    "GIAwayOdd": found[0].get(
                                                        "GIAwayOdd"
                                                    ),
                                                    "Bet": "Draw",
                                                    "Odd": getReverseOdds(drawOdd),
                                                    "Better": float(draw)
                                                    - float(drawOdd),
                                                    "Won": None,
                                                }
                                            )
                                        else:
                                            db.update(
                                                {
                                                    "BetTaken": True,
                                                    "Bet": "Draw",
                                                    "Odd": getReverseOdds(drawOdd),
                                                    "Better": float(draw)
                                                    - float(drawOdd),
                                                },
                                                Matches.BetIndex == betIndex,
                                            )
                                        writtenDraw = True
                                if float(awaywin) - float(awayOdd) >= 5:
                                    if not sendMailAway:
                                        logPrint(
                                            f"Wette auf {away} bei {anbieter}, da GoalImpact Quote {float(awaywin) - float(awayOdd)}% besser ist"
                                        )
                                        logPrint(
                                            "Bookie Odds: "
                                            + str(homeOdd)
                                            + " "
                                            + str(drawOdd)
                                            + " "
                                            + str(awayOdd)
                                        )
                                        sendMail(
                                            f"{home} vs. {away}",
                                            f"Wette auf {away} bei {anbieter}, da GoalImpact Quote {float(awaywin) - float(awayOdd)}% besser ist\n{getReverseOdds(awayOdd)}",
                                        )
                                        logPrint(
                                            "GI: "
                                            + str(homewin)
                                            + " "
                                            + str(draw)
                                            + " "
                                            + str(awaywin)
                                        )
                                        sendMailAway = True
                                    if not writtenAway:
                                        found = db.search(Matches.BetIndex == betIndex)
                                        if found[0].get("BetTaken") != None:
                                            db.insert(
                                                {
                                                    "BetIndex": getHighestIndex() + 1,
                                                    "BetTaken": True,
                                                    "Home": found[0].get("Home"),
                                                    "Away": found[0].get("Away"),
                                                    "GIHomeOdd": found[0].get(
                                                        "GIHomeOdd"
                                                    ),
                                                    "GIDrawOdd": found[0].get(
                                                        "GIDrawOdd"
                                                    ),
                                                    "GIAwayOdd": found[0].get(
                                                        "GIAwayOdd"
                                                    ),
                                                    "Bet": "Away",
                                                    "Odd": getReverseOdds(awayOdd),
                                                    "Better": float(awaywin)
                                                    - float(awayOdd),
                                                    "Won": None,
                                                }
                                            )
                                        else:
                                            db.update(
                                                {
                                                    "BetTaken": True,
                                                    "Bet": "Away",
                                                    "Odd": getReverseOdds(awayOdd),
                                                    "Better": float(awaywin)
                                                    - float(awayOdd),
                                                },
                                                Matches.BetIndex == betIndex,
                                            )
                                        writtenAway = True
                    else:
                        db.update({"BetTaken": False}, Matches.BetIndex == betIndex)
                        logPrint(f"{home} and {away} are not in list")
        except:
            sendMail(
                f"Exception occured",
                f"Exception occurded, check if program is still running!",
            )
    else:
        logPrint(f"No new GoalImpact odds to process")
    counter = counter + 1
    if counter == 4:
        counter = 0
        sendMail(f"Still alive!", f"I am Still alive!")
    time.sleep(900)
