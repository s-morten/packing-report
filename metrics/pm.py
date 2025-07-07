from metrics.metric import Metric

class PM(Metric):
    def update(self, player_value: float, score: int) -> float:
        orig_player_value = player_value
        player_value = int(player_value)
        result = score - player_value
        # add result to player_value as new player_value
        player_value = orig_player_value + (result / 10)
        return player_value
            
    def predict(self, player_value: float, minute: int) -> int:
        return player_value * min((minute / 90), 1)   
