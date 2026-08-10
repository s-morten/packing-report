import logging

from database_io.repositories.metric_repo import DB_metric

logger = logging.getLogger(__name__)

_REQUIRED_COLUMNS = ["type", "team_id", "expanded_minute", "second"]


class TimeToRecovery:
    def __init__(self, metric_repo=None):
        self.metric_repo = metric_repo or DB_metric()

    def calculate(self, game_facts):
        events = game_facts.events
        players_dict = game_facts.players_dict

        missing_columns = [column for column in _REQUIRED_COLUMNS if column not in events.columns]
        if missing_columns:
            raise KeyError(f"Missing required event columns: {missing_columns}")

        events = events.assign(
            time_seconds=events["expanded_minute"] * 60 + events["second"],
            type=events["type"].astype(str),
        )

        team_recoveries = []
        last_touch_time = {}
        for event in events.itertuples(index=False):
            if event.team_id is None:
                continue
            if event.type == "BallRecovery":
                for opponent_team_id, opponent_time in last_touch_time.items():
                    if opponent_team_id != event.team_id:
                        team_recoveries.append(
                            {
                                "team_id": event.team_id,
                                "minute": event.expanded_minute,
                                "recovery_time": float(event.time_seconds - opponent_time),
                            }
                        )
                        break
            last_touch_time[event.team_id] = event.time_seconds

        player_recovery_mapping = {}
        for player_id, info in players_dict.items():
            qualifying = [
                recovery_data["recovery_time"]
                for recovery_data in team_recoveries
                if recovery_data["team_id"] == info["team_id"] and info["on"] < recovery_data["minute"] < info["off"]
            ]
            if qualifying:
                player_recovery_mapping[player_id] = sum(qualifying) / len(qualifying)

        self.player_recovery_mapping = player_recovery_mapping

    def write(self, session, game_id):
        metric_batch = [
            [player, game_id, float(recovery_time), "time_to_recovery"]
            for player, recovery_time in self.player_recovery_mapping.items()
        ]
        self.metric_repo.insert_batch_metric(session, metric_batch)
