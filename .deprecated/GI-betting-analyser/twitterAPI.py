# Import the tweepy library
import tweepy
from tinydb import TinyDB, Query
import json

# Variables that contains the user credentials to access Twitter API
ACCESS_TOKEN = json.load(open("/home/morten/Develop/secrets.json", "r"))["twitter"][
    "ACCESS_TOKEN"
]
ACCESS_SECRET = json.load(open("/home/morten/Develop/secrets.json", "r"))["twitter"][
    "ACCESS_SECRET"
]
CONSUMER_KEY = json.load(open("/home/morten/Develop/secrets.json", "r"))["twitter"][
    "CONSUMER_KEY"
]
CONSUMER_SECRET = json.load(open("/home/morten/Develop/secrets.json", "r"))["twitter"][
    "CONSUMER_SECRET"
]


# Setup tweepy to authenticate with Twitter credentials:

auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)
# Create the api to connect to twitter with your creadentials
api = tweepy.API(auth)
db = TinyDB("./database/db.json")
Matches = Query()


def run():
    index = 0
    for item in db:
        if int(item.get("BetIndex")) > index:
            index = int(item.get("BetIndex"))
    lastTweetId = int(db.search(Matches.LastID)[0].get("LastID"))
    tweets = api.user_timeline(screen_name="GoalimpactOdds", since_id=lastTweetId)
    if tweets:
        for tweet in reversed(tweets):
            sTweet = tweet.text
            sTweet = sTweet[7:]  # remove Time
            idTweet = tweet.id

            sTweet = sTweet.split("\n")

            teams = sTweet[0]

            if len(sTweet) > 4:
                print("True")
                continue
            if len(sTweet) < 4:
                continue
            odds = sTweet[2]

            teams = teams.split(" vs. ")
            odds = odds[4:]
            odds = odds.split(" - ")

            home = teams[0]
            away = teams[1]

            homewin = odds[0]
            draw = odds[1]
            awaywin = odds[2]
            index = index + 1
            db.insert(
                {
                    "BetIndex": index,
                    "BetTaken": None,
                    "Home": home,
                    "Away": away,
                    "GIHomeOdd": homewin,
                    "GIDrawOdd": draw,
                    "GIAwayOdd": awaywin,
                    "Bet": None,
                    "Odd": None,
                    "Better": None,
                    "Won": None,
                }
            )
        db.update({"LastID": int(idTweet)}, Matches.LastID)
        return True
    else:
        return False
