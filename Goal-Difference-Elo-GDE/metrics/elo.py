# elo v0.1 = konstantes k

import numpy as np
INTERCEPT = 0.26708016
COEF = 0.0038207

# mov, player elo, team elo, opp elo, minutes -> updated elo
def calc_elo_update(margin_of_victory, p_elo, p_team_elo, opp_elo, minutes, k=35, c=400):
    print(margin_of_victory, p_elo, p_team_elo, opp_elo, minutes, end=" ")
    # calc average p elo 0.5 * p_elo + 0.5 * p_team_elo
    p_rating = 0.5 * p_elo + 0.5 * p_team_elo
    # calc expected value of goals based on minutes
    rating_diff = p_rating - opp_elo
    regressed_game_outcome = ((INTERCEPT + COEF * rating_diff) / 90) * minutes 
    # player won/draw/lost based of expected value
    rounded_game_outcome = int(regressed_game_outcome + 0.5)
    if margin_of_victory > rounded_game_outcome: 
        game_result = 1
    elif margin_of_victory < rounded_game_outcome:
        game_result = 0
    else:
        game_result = 0.5
    p_rating = np.power(10, (p_rating/c))
    opp_rating = np.power(10, (opp_elo/c))

    # elo calc
    expected_game_outcome = p_rating / (p_rating + opp_rating)
    updated_score = p_elo + k * (game_result - expected_game_outcome)
    print("-> ", updated_score)
    return updated_score