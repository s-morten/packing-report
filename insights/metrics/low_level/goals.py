from database_io.repositories.metric_repo import DB_metric
from utils.football_data_utils import get_score


class Goals:
    def __init__(self, metric_repo=None):
        self.metric_repo = metric_repo or DB_metric()

    def calculate(self, game_timeline):
        event_dataframe = get_score(game_timeline.events, game_timeline.df_teams)
        goal_dict = dict(zip(event_dataframe["expanded_minute"].values, event_dataframe["goal_team_id"].values))

        player_goal_minute_mapping = {}
        for player in game_timeline.players_dict:
            player_on = game_timeline.players_dict[player]["on"]
            player_off = game_timeline.players_dict[player]["off"]
            player_team_id = game_timeline.players_dict[player]["team_id"]
            player_goals_for = 0
            player_goals_against = 0
            for goal in goal_dict:
                if (goal > player_on) and (goal < player_off):
                    if goal_dict[goal] == player_team_id:
                        player_goals_for += 1
                    else:
                        player_goals_against += 1
            player_goal_minute_mapping[player] = {
                "team_id": player_team_id,
                "goals_for": player_goals_for,
                "goals_against": player_goals_against,
                "minutes": player_off - game_timeline.players_dict[player]["on"],
                "on": game_timeline.players_dict[player]["on"],
                "off": player_off,
            }
        self.player_goal_minute_mapping = player_goal_minute_mapping

    def write(self, session, game_id):
        metric_batch = [
            [
                player,
                game_id,
                self.player_goal_minute_mapping[player]["goals_for"]
                - self.player_goal_minute_mapping[player]["goals_against"],
                "goals",
            ]
            for player in self.player_goal_minute_mapping
        ]
        self.metric_repo.insert_batch_metric(session, metric_batch)
