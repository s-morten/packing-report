import numpy as np
INTERCEPT = 0.3419794
COEF = 0.00541355

# mov, player elo, team elo, opp elo, minutes -> updated elo
def calc_elo_update(margin_of_victory, p_elo, p_team_elo, opp_elo, minutes, k=35, c=400):
    # calc average p elo 0.5 * p_elo + 0.5 * p_team_elo
    p_rating = 0.5 * p_elo + 0.5 * p_team_elo
    # calc expected value of goals based on minutes
    rating_diff = p_rating - opp_elo
    regressed_game_outcome = ((INTERCEPT + COEF * rating_diff) / 90) * minutes 
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