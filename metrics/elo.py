import numpy as np
import json
from database_io.db_handler import DB_handler
from metrics.mov_elo.regressor import MOV_Regressor

def read_parameters():
    parameters = json.load(open("gde/metrics/mov_elo/regressor.json", "r"))
    return parameters["intercept"], parameters["coefficient_elo_diff1"], parameters["coefficient_elo_diff2"], parameters["coefficient_elo_diff3"], parameters["coefficient_min"], parameters["version"]

def retrain_regressor(version, dbh, elo_version):
    number_games = dbh.games.get_number_of_games(elo_version)    
    if int(number_games / 300) > version:
        # update paramaters
        reg = MOV_Regressor(version, elo_version)
        reg.update_regressor(dbh)
        return True
    return False

# mov, player elo, team elo, opp elo, minutes -> updated elo
def calc_elo_update(margin_of_victory, p_elo, p_team_elo, opp_elo, minutes, dbh, elo_version, k=35, c=400):
    intercept, coef1, coef2, coef3, min_coef, version = read_parameters()
    if retrain_regressor(version, dbh, elo_version):
        intercept, coef1, coef2, coef3, min_coef, version = read_parameters()
        
    # calc average p elo 0.5 * p_elo + 0.5 * p_team_elo
    p_rating = 0.5 * p_elo + 0.5 * p_team_elo
    # calc expected value of goals based on minutes
    rating_diff = p_rating - opp_elo
    regressed_game_outcome = (intercept + 
                              coef1 * rating_diff + 
                              coef2 * rating_diff**2 + 
                              coef3 * rating_diff**3 + 
                              min_coef * minutes) 
    # TODO WIP - adjust regressor
    # regressed_game_outcome = regressed_game_outcome * 5
    # player won/draw/lost based of expected value
    rounded_game_outcome = np.rint(regressed_game_outcome)
    if margin_of_victory > rounded_game_outcome: 
        game_result = 1
    elif margin_of_victory < rounded_game_outcome:
        game_result = 0
    else: 
        return p_elo, regressed_game_outcome, rounded_game_outcome
    k = calc_k(k, 25, minutes, abs(margin_of_victory - rounded_game_outcome))
    p_rating = np.power(10, (p_rating/c))
    opp_rating = np.power(10, (opp_elo/c))

    # elo calc
    expected_game_outcome = p_rating / (p_rating + opp_rating)
    updated_score = p_elo + k * (game_result - expected_game_outcome)
    return updated_score, regressed_game_outcome, rounded_game_outcome

def calc_k(k, age, minutes, delta_from_exp):
    minute_quota = minutes / 90
    # if age <= 18:
    #     age_quota = 1.2
    # elif age <= 23:
    #     age_quota = 1
    # elif age <= 31:
    #     age_quota = 0.8
    # else: 
    #     age_quota = 1
    dfe_quota = 1.3 if (delta_from_exp == 2) else 1.6 if (delta_from_exp == 3) else 2 if (delta_from_exp >= 4) else 1
    age_quota = 1
    k = k * age_quota * minute_quota * dfe_quota
    return k