import soccerdata as sd
import numpy as np

class ClubEloScraper:
    def __init__(self):
        self.ce = sd.ClubElo()

    def get_team_elo_by_date(self, date, team_name):
        elo_at_date = self.ce.read_by_date(date)
        elo_at_date = elo_at_date.reset_index()
        if elo_at_date[elo_at_date["team"] == team_name].empty:
            print(team_name)
        elo = float(elo_at_date[elo_at_date["team"] == team_name].elo.iloc[0])
        return elo

    def get_avg_league_elo_by_date(self, date, league):
        elo_at_date = self.ce.read_by_date(date)
        elo_at_date = elo_at_date.reset_index()
        return np.mean(elo_at_date[elo_at_date["league"] == league]["elo"])
