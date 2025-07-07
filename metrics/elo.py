import numpy as np
import json
from database_io.db_handler import DB_handler
from metrics.mov_elo.regressor import MOV_Regressor

# mov, player elo, team elo, opp elo, minutes -> updated elo
def calc_elo_update(margin_of_victory: int, home: int, p_elo: float, p_team_elo: float, opp_elo: float, minutes_missed: int, minutes_played: int, mov_reg: MOV_Regressor):
    c = 400 # calculation parameter, 
    p_elo = float(p_elo)
    p_team_elo = float(p_team_elo)
    # TODO retrain at different location
    
    # p_rating = 0.5 * p_elo + 0.5 * p_team_elo
    p_rating = p_elo
    # calc expected value of goals based on minutes
    rating_diff = p_rating - opp_elo

    regressed_game_outcome = mov_reg.predict(home, rating_diff, elo_diff_faktor=352, goal_diff_faktor=8, minutes_missed=minutes_missed, minutes_faktor=101)
    # print(regressed_game_outcome)
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

    k = calc_k(minutes_played)

    # elo calc
    expected_game_outcome = p_rating / (p_rating + opp_rating)
    updated_score = p_elo + k * (game_result - expected_game_outcome)
    return updated_score, regressed_game_outcome[0], regressed_game_outcome[1]
    
def calc_k(minutes):
    # TODO include age aspect
    k = min(max(minutes / 3, 5), 20)
    return k