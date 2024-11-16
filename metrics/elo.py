import numpy as np
import json
from database_io.db_handler import DB_handler
from metrics.mov_elo.regressor import MOV_Regressor

# mov, player elo, team elo, opp elo, minutes -> updated elo
def calc_elo_update(margin_of_victory: int, home: int, p_elo: float, p_team_elo: float, opp_elo: float, minutes: int, mov_reg: MOV_Regressor, k=35, c=400):
    p_elo = float(p_elo)
    p_team_elo = float(p_team_elo)
    # TODO retrain at different location
        
    # calc average p elo 0.5 * p_elo + 0.5 * p_team_elo
    p_rating = 0.5 * p_elo + 0.5 * p_team_elo
    # calc expected value of goals based on minutes
    rating_diff = p_rating - opp_elo

    regressed_game_outcome = mov_reg.predict(home, rating_diff, elo_diff_faktor=411.2269214742066, goal_diff_faktor=7, minutes=minutes, minutes_faktor=107)
    
    # expected game outcome -> elo stays the same
    if margin_of_victory >= regressed_game_outcome[0] and margin_of_victory <= regressed_game_outcome[1]:
        return p_elo, regressed_game_outcome[0], regressed_game_outcome[1]
    # player overachieved
    elif margin_of_victory > regressed_game_outcome[1]:
        game_result = 1
    # player underachieved
    elif margin_of_victory < regressed_game_outcome[0]:
        game_result = 0

    p_rating = np.power(10, (p_rating/c))
    opp_rating = np.power(10, (opp_elo/c))

    # elo calc
    expected_game_outcome = p_rating / (p_rating + opp_rating)
    updated_score = p_elo + k * (game_result - expected_game_outcome)
    return updated_score, regressed_game_outcome[0], regressed_game_outcome[1]
    
# def calc_k(k, age, minutes, delta_from_exp):
#     minute_quota = minutes / 90
#     # if age <= 18:
#     #     age_quota = 1.2
#     # elif age <= 23:
#     #     age_quota = 1
#     # elif age <= 31:
#     #     age_quota = 0.8
#     # else: 
#     #     age_quota = 1
#     dfe_quota = 1.3 if (delta_from_exp == 2) else 1.6 if (delta_from_exp == 3) else 2 if (delta_from_exp >= 4) else 1
#     age_quota = 1
#     k = k * age_quota * minute_quota * dfe_quota
#     return k