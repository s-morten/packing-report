import numpy as np
import json
from database_io.db_handler import DB_handler
from metrics.mov_elo.regressor import MOV_Regressor
from metrics.metric import Metric

class PlayerELO(Metric):
    # mov, player elo, team elo, opp elo, minutes -> updated elo
    def update(self, margin_of_victory: int, exp_game_res_lower, exp_game_res_upper, minutes_played):
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

        k = self._calc_k(minutes_played)

        # elo calc
        expected_game_outcome = p_rating / (p_rating + opp_rating)
        updated_score = self.p_elo + k * (game_result - expected_game_outcome)
        return updated_score
        
    def _calc_k(self, minutes_played, max_k=20):
        """
        Scales K-factor linearly based on minutes played.
        A 90-minute game corresponds to max_k.
        """
        # Ensure minutes are capped at 90 to avoid weird scaling in extra time
        minutes_played = min(minutes_played, 90)
        
        # Linearly scale K from 0 to max_k
        k = (minutes_played / 90) * max_k
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
 