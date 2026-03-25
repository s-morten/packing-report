import numpy as np
import json
from database_io.db_handler import DB_handler
from metrics.mov_elo.regressor import MOV_Regressor
from metrics.metric import Metric

class PlayerELO(Metric):
    # mov, player elo, team elo, opp elo, minutes -> updated elo
    def update(self, margin_of_victory: int, exp_game_res_lower, exp_game_res_upper, minutes_played, minutes_3_mon):
        c = 400 # calculation parameter, 
       # print(regressed_game_outcome)
        # expected game outcome -> elo stays the same
        if margin_of_victory >= exp_game_res_lower and margin_of_victory <= exp_game_res_upper:
            return self.p_elo
        # player overachieved
        elif margin_of_victory > exp_game_res_upper:
            game_result = 1
        # player underachieved
        elif margin_of_victory < exp_game_res_lower:
            game_result = 0

        p_rating = np.power(10, (self.p_rating/c))
        opp_rating = np.power(10, (self.opp_value/c))

        k = self._calc_k(minutes_played, minutes_3_mon)

        # elo calc
        expected_game_outcome = p_rating / (p_rating + opp_rating)
        updated_score = self.p_elo + k * (game_result - expected_game_outcome)
        return updated_score
        
    def _calc_k(self, minutes_played, minutes_3_mon, max_k=20):
        """
        Scales K-factor linearly based on minutes played.
        A 90-minute game corresponds to max_k.
        """
        # Ensure minutes are capped at 90 to avoid weird scaling in extra time
        minutes_played = min(minutes_played, 90)
        
        # Linearly scale K from 0 to max_k
        k = (minutes_played / 90) * max_k
        minutes_3_mon = minutes_3_mon if minutes_3_mon is not None else 0
        if minutes_3_mon < 500:
            established = False
        else:
            established = True
        k = k / 2 if established else k
        return k
    
    def predict(self, home, player_value, team_value, opp_value, minutes_missed, mov_regressor):
        p_elo = float(player_value)
        self.p_elo = p_elo
        p_team_elo = float(team_value)
        # TODO retrain MOV Regressor automatically  
        p_rating = 0.33 * p_elo + 0.67 * p_team_elo
        self.p_rating = p_rating
        # p_rating = p_elo
        # calc expected value of goals based on minutes
        rating_diff = p_rating - opp_value
        self.opp_value = opp_value

        regressed_game_outcome = mov_regressor.predict(home, rating_diff, minutes_missed=minutes_missed)
        return regressed_game_outcome
 


 ## init 
 # init ELO
# if self.db_handler.metric.get_player_count_per_league(self.game_league, self.version) < 50:
#     if league_elo is None:
#         # get Elo from Club Elo, because not enough players are 
#         league_elo = ClubEloScraper().get_avg_league_elo_by_date(pd.to_datetime(self.game_date, format="%Y-%m-%d"), self.game_league)
#     start_elo = league_elo if self.general_info_dict[int(player_id)]["starter"] else league_elo * 0.7
#     self.player_info_df.loc[self.player_info_df["id"] == int(player_id), "elo"] = start_elo
#     print("league_elo", start_elo)
# else:
#     self.player_info_df.loc[self.player_info_df["id"] == int(player_id), "elo"] = np.float64(self.db_handler.metric.average_elo(self.game_league, self.general_info_dict[int(player_id)]["team_id"], self.game_date, self.version)) # * 0.7
#     print("50 players", np.float64(self.db_handler.metric.average_elo(self.game_league, self.general_info_dict[int(player_id)]["team_id"], self.game_date, self.version)) * 0.7)
            


# # METRIC Elo ################################
# # update elo, elo calc
# p_elo = self.player_info_df[self.player_info_df["id"] == player_id]["elo"].values[0]
# p_team_elo = np.mean([self.game_timeline_dicts["elo"][team_id][str(minute)] for minute in range(player_on, player_off + 1)])
# opp_elo = np.mean([self.game_timeline_dicts["elo"][opposition_team_id][str(minute)] for minute in range(player_on, player_off + 1)])

# # update elo
# exp_res_lower, exp_res_upper = self.metric_elo.predict( home, p_elo, p_team_elo, opp_elo, self.end_of_game - minutes, self.mov_regressor)
# updated_elo = self.metric_elo.update(p_mov, exp_res_lower, exp_res_upper, minutes, minutes_3_mon)

# self.player_info_df.loc[self.player_info_df["id"] == player_id, "updated_elo"] = updated_elo
# self.player_info_df.loc[self.player_info_df["id"] == player_id, "exp_res_lower_elo"] = exp_res_lower
# self.player_info_df.loc[self.player_info_df["id"] == player_id, "exp_res_upper_elo"] = exp_res_upper