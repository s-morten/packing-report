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



# # init pm
# self.player_info_df.loc[self.player_info_df["id"] == int(player_id), "pm"] = 0    

# # METRIC pm ################################ 
# p_pm = self.player_info_df[self.player_info_df["id"] == player_id]["pm"].values[0]
# p_team_pm = np.mean([self.game_timeline_dicts["pm"][team_id][str(minute)] for minute in range(player_on, player_off + 1)])
# opp_pm = np.mean([self.game_timeline_dicts["pm"][opposition_team_id][str(minute)] for minute in range(player_on, player_off + 1)])
# exp_res = self.metric_pm.predict(p_pm, p_team_pm, opp_pm, minutes)
# updated_pm = self.metric_pm.update(p_pm, p_mov, exp_res)
# self.player_info_df.loc[self.player_info_df["id"] == player_id, "updated_pm"] = updated_pm
# self.player_info_df.loc[self.player_info_df["id"] == player_id, "exp_res_lpm"] = exp_res