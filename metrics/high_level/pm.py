from metrics.metric import Metric

class PM(Metric):
    def update(self, player_value: float, score: int, expected_score: float) -> float:
        orig_player_value = player_value
        player_value = int(player_value)
        result = score - expected_score
        # add result to player_value as new player_value
        player_value = orig_player_value + (result / 10)
        return player_value

    # TODO unabhängig vom gegener score -> (player_value - gegener_score)?
    def predict(self, player_value: float, team_value: float, opp_value: float, minute: int) -> int:
        return ((player_value * 0.34 + team_value * 0.66) - opp_value) * min((minute / 90), 1)   
