from flask import Flask, render_template, request, Response
import os
import io
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
import matplotlib.pyplot as plt
from tinydb import TinyDB, Query


app = Flask(__name__)

# poll_question = getQuestion()
poll_answeres = ["Home", "Draw", "Away"]

# db = TinyDB('./../database/db.json')
db = TinyDB("./../database/db.json")


def resize():
    db = TinyDB("./../database/db.json")
    Matches = Query()

    totalOdds = db.search(Matches.BetIndex == 3)[0].get("totalOdds")
    totalBetsLow = db.search(Matches.BetIndex == 4)[0].get("totalBetsLow")
    totalBetsMid = db.search(Matches.BetIndex == 5)[0].get("totalBetsMid")
    totalBetsHigh = db.search(Matches.BetIndex == 6)[0].get("totalBetsHigh")
    betsWonLow = db.search(Matches.BetIndex == 7)[0].get("betsWonLow")
    betsWonMid = db.search(Matches.BetIndex == 8)[0].get("betsWonMid")
    betsWonHigh = db.search(Matches.BetIndex == 9)[0].get("betsWonHigh")
    totalWonLow = db.search(Matches.BetIndex == 10)[0].get("totalWonLow")
    totalWonMid = db.search(Matches.BetIndex == 11)[0].get("totalWonMid")
    totalWonHigh = db.search(Matches.BetIndex == 12)[0].get("totalWonHigh")
    bets = db.search(Matches.BetIndex >= 13)
    if bets:
        for bet in bets:
            print(bet)
            totalOdds += 1
            if bet.get("BetTaken") == True:
                if bet.get("Better") < 10:
                    print("found low Bet")
                    if bet.get("Won") == True:
                        totalBetsLow += 1
                        betsWonLow += 1
                        totalWonLow += 1 * (bet.get("Odd") - 1)
                    elif bet.get("Won") == False:
                        totalBetsLow += 1
                        totalWonLow -= 1
                    elif bet.get("Won") == None:
                        totalOdds -= 1
                        continue
                elif bet.get("Better") < 15:
                    print("found mid Bet")
                    if bet.get("Won") == True:
                        totalBetsMid += 1
                        betsWonMid += 1
                        totalWonMid += 1 * (bet.get("Odd") - 1)
                    elif bet.get("Won") == False:
                        totalBetsMid += 1
                        totalWonMid -= 1
                    elif bet.get("Won") == None:
                        totalOdds -= 1
                        continue
                else:
                    print("found high Bet")
                    if bet.get("Won") == True:
                        totalBetsHigh += 1
                        betsWonHigh += 1
                        totalWonHigh += 1 * (bet.get("Odd") - 1)
                    elif bet.get("Won") == False:
                        totalBetsHigh += 1
                        totalWonHigh -= 1
                    elif bet.get("Won") == None:
                        totalOdds -= 1
                        continue
            db.remove(Matches.BetIndex == bet.get("BetIndex"))
            print("Bet removed!")
    else:
        print("Nothin to do!")

    db.update({"totalOdds": totalOdds}, Matches.BetIndex == 3)
    db.update({"totalBetsLow": totalBetsLow}, Matches.BetIndex == 4)
    db.update({"totalBetsMid": totalBetsMid}, Matches.BetIndex == 5)
    db.update({"totalBetsHigh": totalBetsHigh}, Matches.BetIndex == 6)
    db.update({"betsWonLow": betsWonLow}, Matches.BetIndex == 7)
    db.update({"betsWonMid": betsWonMid}, Matches.BetIndex == 8)
    db.update({"betsWonHigh": betsWonHigh}, Matches.BetIndex == 9)
    db.update({"totalWonLow": totalWonLow}, Matches.BetIndex == 10)
    db.update({"totalWonMid": totalWonMid}, Matches.BetIndex == 11)
    db.update({"totalWonHigh": totalWonHigh}, Matches.BetIndex == 12)
    print(totalOdds)
    print(totalBetsLow)
    print(totalBetsMid)
    print(totalBetsHigh)
    print(betsWonLow)
    print(betsWonMid)
    print(betsWonHigh)
    print(totalWonLow)
    print(totalWonMid)
    print(totalWonHigh)


def getQuestion():
    db = TinyDB("./../database/db.json")
    Matches = Query()
    openBets = db.search(
        (Matches.BetIndex >= 3) & (Matches.Won == None) & (Matches.BetTaken == True)
    )
    if openBets:
        home = openBets[0].get("Home")
        away = openBets[0].get("Away")
        retValue = f"{home} vs {away}"
        return retValue
    else:
        return "There is no open bet right now, keep cool"


def generateGraphs():
    db = TinyDB("./../database/db.json")
    Matches = Query()
    resize()
    totalOdds = db.search(Matches.BetIndex == 3)[0].get("totalOdds")
    totalBetsLow = db.search(Matches.BetIndex == 4)[0].get("totalBetsLow")
    totalBetsMid = db.search(Matches.BetIndex == 5)[0].get("totalBetsMid")
    totalBetsHigh = db.search(Matches.BetIndex == 6)[0].get("totalBetsHigh")
    betsWonLow = db.search(Matches.BetIndex == 7)[0].get("betsWonLow")
    betsWonMid = db.search(Matches.BetIndex == 8)[0].get("betsWonMid")
    betsWonHigh = db.search(Matches.BetIndex == 9)[0].get("betsWonHigh")
    totalWonLow = db.search(Matches.BetIndex == 10)[0].get("totalWonLow")
    totalWonMid = db.search(Matches.BetIndex == 11)[0].get("totalWonMid")
    totalWonHigh = db.search(Matches.BetIndex == 12)[0].get("totalWonHigh")

    generatePlots(
        betsWonLow + betsWonMid + betsWonHigh,
        totalBetsLow
        - betsWonLow
        + totalBetsMid
        - betsWonMid
        + totalBetsHigh
        - betsWonHigh,
        "./static/images/plot_all.png",
        "Total",
    )
    generatePlots(
        betsWonLow,
        totalBetsLow - betsWonLow,
        "./static/images/plot_low.png",
        "5% - 10%",
    )
    generatePlots(
        betsWonMid,
        totalBetsMid - betsWonMid,
        "./static/images/plot_mid.png",
        "10% - 15%",
    )
    generatePlots(
        betsWonHigh,
        totalBetsHigh - betsWonHigh,
        "./static/images/plot_high.png",
        "15% - 20%+",
    )


def generatePlots(won, lost, save_adress, title):
    # won / lost graph
    plt.title(title)
    height = [won, lost]
    bars = ("won", "lost")
    y_pos = np.arange(len(bars))
    # Create bars
    barlist = plt.bar(y_pos, height)
    barlist[0].set_color("g")
    barlist[1].set_color("r")
    # Create names on the x-axis
    plt.xticks(y_pos, bars)
    # Show graphic
    plt.savefig(save_adress)
    plt.close()


def getStats():
    db = TinyDB("./../database/db.json")
    Matches = Query()
    resize()
    totalOdds = db.search(Matches.BetIndex == 3)[0].get("totalOdds")
    totalBetsLow = db.search(Matches.BetIndex == 4)[0].get("totalBetsLow")
    totalBetsMid = db.search(Matches.BetIndex == 5)[0].get("totalBetsMid")
    totalBetsHigh = db.search(Matches.BetIndex == 6)[0].get("totalBetsHigh")
    betsWonLow = db.search(Matches.BetIndex == 7)[0].get("betsWonLow")
    betsWonMid = db.search(Matches.BetIndex == 8)[0].get("betsWonMid")
    betsWonHigh = db.search(Matches.BetIndex == 9)[0].get("betsWonHigh")
    totalWonLow = db.search(Matches.BetIndex == 10)[0].get("totalWonLow")
    totalWonMid = db.search(Matches.BetIndex == 11)[0].get("totalWonMid")
    totalWonHigh = db.search(Matches.BetIndex == 12)[0].get("totalWonHigh")

    stats = [0] * 6
    stats[0] = ((totalBetsLow + totalBetsMid + totalBetsHigh) / totalOdds) * 100
    stats[1] = totalWonLow + totalWonMid + totalWonHigh
    stats[2] = totalWonLow
    stats[3] = totalWonMid
    stats[4] = totalWonHigh
    stats[5] = db.search(Matches.BetIndex == 2)[0].get("RemainingRequests")
    return stats


@app.route("/")
def root():

    return render_template(
        "layout.html", answeres=poll_answeres, question=getQuestion(), stats=getStats()
    )


@app.route("/poll")
def poll():
    db = TinyDB("./../database/db.json")
    Matches = Query()
    vote = request.args.get("field")
    openBets = db.search(
        (Matches.BetIndex >= 3) & (Matches.Won == None) & (Matches.BetTaken == True)
    )
    if openBets:
        bet = openBets[0].get("Bet")
        betIndex = openBets[0].get("BetIndex")

        if vote == bet:
            db.update({"Won": True}, Matches.BetIndex == betIndex)
        else:
            db.update({"Won": False}, Matches.BetIndex == betIndex)
    # return render_template('poll.html', answeres = poll_answeres, question = getQuestion())
    return root()


@app.route("/refresh_plots")
def refresh_plots():
    generateGraphs()
    return root()


if __name__ == "__main__":
    app.run(debug=True)
