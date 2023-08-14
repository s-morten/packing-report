import numpy as np
from player import Player
import datetime










def get_uncertainty(player_id, game_date):
    player = Player(int(player_id))
    date = game_date - datetime.timedelta(weeks=8)
    game_date = game_date - datetime.timedelta(days=1)
    games = player.get_games_by_date(date, game_date)
    mins = 0.0
    for game in games:
        mins += game.minutes_played
    return np.clip([(700 - mins) / 10], 0, 100)
    