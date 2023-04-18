import pickle
import numpy as np
from utils.lwp_utils import timestamp_to_time, get_mat_pos, get_rolling_avg
from kloppy import statsbomb
import sys

sys.path.append("/home/morten/Develop/Live-Win-Prob")


def get_timeslot_length(match_id):
    """Calculates the length of the 50 timeslots per half for the given match

    Args:
        match_id (int): match id for the wanted match

    Returns:
        int , int: length of the timeslots first half and second half
    """
    dataset = statsbomb.load(
        event_data=f"/home/morten/Develop/Open-Data/statsbomb/open-data/data/events/{match_id}.json",
        lineup_data=f"/home/morten/Develop/Open-Data/statsbomb/open-data/data/lineups/{match_id}.json",
        # Optional arguments
        coordinates="statsbomb",
        event_types=["generic"],
    )

    first_half_time = 0
    second_half_time = 0
    for event in dataset.events:
        if event.raw_event["type"]["id"] == 34 and event.raw_event["period"] == 1:
            first_half_time = event.raw_event["timestamp"]
        if event.raw_event["type"]["id"] == 34 and event.raw_event["period"] == 2:
            second_half_time = event.raw_event["timestamp"]

    total_time_fh = timestamp_to_time(first_half_time)
    total_time_sh = timestamp_to_time(second_half_time)

    timeslot_length_fh = total_time_fh // 50
    timeslot_length_sh = total_time_sh // 50

    return timeslot_length_fh, timeslot_length_sh


def fit_actions_to_timeframe(match_id, period, slot_length, action):
    """sort events in the 50 timeslots for the given period

    Args:
        match_id (int): the match id of match
        period (int): period of the game
        slot_length (int): the length of the slot
        action (string): action type exp.: shoot, pass, carry

    Returns:
        list: list of timeslots filled with events
    """
    dataset = statsbomb.load(
        event_data=f"/home/morten/Develop/Open-Data/statsbomb/open-data/data/events/{match_id}.json",
        lineup_data=f"/home/morten/Develop/Open-Data/statsbomb/open-data/data/lineups/{match_id}.json",
        # Optional arguments
        coordinates="statsbomb",
        event_types=[action],
    )
    time = [0 for x in range(50)]
    slots = [[] for x in range(50)]
    for x in range(50):
        time[x] = (x + 1) * slot_length
    for event in dataset.events:
        t = timestamp_to_time(event.raw_event["timestamp"])
        for x in range(50):
            if event.raw_event["period"] == period and t <= time[x]:
                slots[x].append(event)
                break

    return slots


def get_action_per_timeframe(match_id, action):
    """calculate the lists for both halfes, filled with the actions per timeframe

    Args:
        match_id (int): match id of the match
        action (string): action type exp.: shoot, pass, carry

    Returns:
        list, list: actionlist per timeframe first half, second half
    """
    timeframe_first_half, timeframe_second_half = get_timeslot_length(match_id)
    actionframe_first_half = fit_actions_to_timeframe(
        match_id, 1, timeframe_first_half, action
    )
    actionframe_second_half = fit_actions_to_timeframe(
        match_id, 2, timeframe_second_half, action
    )

    return actionframe_first_half, actionframe_second_half


def calc_xT_per_slot(match_id, xT_modell):
    """calculates the xT value per timeslot

    Args:
        match_id (int): the statsbomb match id
        xT_modell (list[list]): the calculated xT modell

    Returns:
        list, list: the 100 timeslots containing xT for the home team, away team
    """
    fh, sh = get_action_per_timeframe(match_id, "pass")
    game = [fh, sh]
    timeslots_home_pass = [[] for x in range(100)]
    timeslots_away_pass = [[] for x in range(100)]
    for half_idx, half in enumerate(game):
        for idx, slot in enumerate(half):
            for event in slot:
                if "outcome" in event.raw_event["pass"]:
                    continue
                # calc xT
                x, y = get_mat_pos(
                    event.raw_event["location"][0], event.raw_event["location"][1]
                )
                w, z = get_mat_pos(
                    event.raw_event["pass"]["end_location"][0],
                    event.raw_event["pass"]["end_location"][1],
                )
                xT = xT_modell[z][w] - xT_modell[y][x]
                if event.team.ground.value == "home":
                    timeslots_home_pass[idx + (50 * half_idx)].append(xT)
                elif event.team.ground.value == "away":
                    timeslots_away_pass[idx + (50 * half_idx)].append(xT)
                else:
                    print("Oh no!")

    fh, sh = get_action_per_timeframe(match_id, "carry")
    game = [fh, sh]
    timeslots_home_carry = [[] for x in range(100)]
    timeslots_away_carry = [[] for x in range(100)]
    for half_idx, half in enumerate(game):
        for idx, slot in enumerate(half):
            for event in slot:
                # calc xT
                x, y = get_mat_pos(
                    event.raw_event["location"][0], event.raw_event["location"][1]
                )
                w, z = get_mat_pos(
                    event.raw_event["carry"]["end_location"][0],
                    event.raw_event["carry"]["end_location"][1],
                )
                xT = xT_modell[z][w] - xT_modell[y][x]
                if event.team.ground.value == "home":
                    timeslots_home_carry[idx + (50 * half_idx)].append(xT)
                elif event.team.ground.value == "away":
                    timeslots_away_carry[idx + (50 * half_idx)].append(xT)
                else:
                    print("Oh no!")

    timeslots_home = [[] for x in range(100)]
    timeslots_away = [[] for x in range(100)]
    for i in range(100):
        for x in timeslots_home_pass[i]:
            timeslots_home[i].append(x)
        for x in timeslots_home_carry[i]:
            timeslots_home[i].append(x)
        for x in timeslots_away_pass[i]:
            timeslots_away[i].append(x)
        for x in timeslots_away_carry[i]:
            timeslots_away[i].append(x)

    return timeslots_home, timeslots_away


def get_goals_per_timeframe(match_id):
    """calculates the scored goals per timeframe and per team

    Args:
        match_id (int): statsbomb match id

    Returns:
        list, list: goal slots home, away
    """
    fh, sh = get_action_per_timeframe(match_id, "shot")
    game = [fh, sh]
    timeslots_home = [[] for x in range(100)]
    timeslots_away = [[] for x in range(100)]
    for half_idx, half in enumerate(game):
        for idx, slot in enumerate(half):
            for event in slot:
                if event.result.value == "GOAL":
                    if event.team.ground.value == "home":
                        timeslots_home[idx + (50 * half_idx)].append(event)
                    elif event.team.ground.value == "away":
                        timeslots_away[idx + (50 * half_idx)].append(event)
                    else:
                        print("Oh no!")

    return timeslots_home, timeslots_away


def get_score_diff_at_tf(match_id, tf, team):
    """calculates the score differential at the given timeframe

    Args:
        match_id (int): statsbomb match id
        tf (int): timeframe for diff calc, 0-99
        team (string): string of the team for the calc, home or away

    Returns:
        int: score diff at the timeframe
    """
    timeslot_home, timeslot_away = get_goals_per_timeframe(match_id)
    gh, ga = 0, 0
    for idx, slot in enumerate(timeslot_home):
        if idx <= tf:
            gh += len(slot)
    for idx, slot in enumerate(timeslot_away):
        if idx <= tf:
            ga += len(slot)
    if team == "home":
        return gh - ga
    elif team == "away":
        return ga - gh


def get_team_goals(match_id, tf, team):
    """calculates the score differential at the given timeframe

    Args:
        match_id (int): statsbomb match id
        tf (int): timeframe for team goals calc, 0-99
        team (string): string of the team for the calc, home or away

    Returns:
        int: team goals at the timeframe
    """
    timeslot_home, timeslot_away = get_goals_per_timeframe(match_id)
    gh, ga = 0, 0
    for idx, slot in enumerate(timeslot_home):
        if idx <= tf:
            gh += len(slot)
    for idx, slot in enumerate(timeslot_away):
        if idx <= tf:
            ga += len(slot)
    if team == "home":
        return gh
    elif team == "away":
        return ga


def get_cards_per_timeframe(match_id):
    """get red and yellow cards per timeframe

    Args:
        match_id (int): statsbomb match_id for the game

    Returns:
        list, list, list, list: yellow cards home per time frame, reds, yellows away, reds away
    """
    fh, sh = get_action_per_timeframe(match_id, "card")
    game = [fh, sh]
    timeslots_yellow_home = [[] for x in range(100)]
    timeslots_yellow_away = [[] for x in range(100)]
    timeslots_red_home = [[] for x in range(100)]
    timeslots_red_away = [[] for x in range(100)]
    for half_idx, half in enumerate(game):
        for idx, slot in enumerate(half):
            for event in slot:
                if "foul_committed" in event.raw_event:
                    if (
                        event.raw_event["foul_committed"]["card"]["name"]
                        == "Yellow Card"
                    ):
                        if event.team.ground.value == "home":
                            timeslots_yellow_home[idx +
                                                  (50 * half_idx)].append(event)
                        elif event.team.ground.value == "away":
                            timeslots_yellow_away[idx +
                                                  (50 * half_idx)].append(event)
                        else:
                            print("Oh no!")
                    elif (
                        event.raw_event["foul_committed"]["card"]["name"] == "Red Card"
                        or event.raw_event["bad_behaviour"]["card"]["name"]
                        == "Second Yellow"
                    ):
                        if event.team.ground.value == "home":
                            timeslots_red_home[idx +
                                               (50 * half_idx)].append(event)
                        elif event.team.ground.value == "away":
                            timeslots_red_away[idx +
                                               (50 * half_idx)].append(event)
                        else:
                            print("Oh no!")
                elif "bad_behaviour" in event.raw_event:
                    if (
                        event.raw_event["bad_behaviour"]["card"]["name"]
                        == "Yellow Card"
                    ):
                        if event.team.ground.value == "home":
                            timeslots_yellow_home[idx +
                                                  (50 * half_idx)].append(event)
                        elif event.team.ground.value == "away":
                            timeslots_yellow_away[idx +
                                                  (50 * half_idx)].append(event)
                        else:
                            print("Oh no!")
                    elif (
                        event.raw_event["bad_behaviour"]["card"]["name"] == "Red Card"
                        or event.raw_event["bad_behaviour"]["card"]["name"]
                        == "Second Yellow"
                    ):
                        if event.team.ground.value == "home":
                            timeslots_red_home[idx +
                                               (50 * half_idx)].append(event)
                        elif event.team.ground.value == "away":
                            timeslots_red_away[idx +
                                               (50 * half_idx)].append(event)
                        else:
                            print("Oh no!")

    return (
        timeslots_yellow_home,
        timeslots_red_home,
        timeslots_yellow_away,
        timeslots_red_away,
    )


def get_num_cards(match_id, card, tf, team):
    """get number of yellow or red cards per team and timeframe

    Args:
        match_id (int): statsbomb match id
        card (string): yellow or red
        tf (int): timeframe, 0-99
        team (string): team, home or away

    Returns:
        int: number of yellow or red cards
    """
    ych, rch, yca, rca = get_cards_per_timeframe(match_id)
    if card == "red":
        reds = 0
        evaluate = rch if team == "home" else rca
        for idx, slot in enumerate(evaluate):
            if idx <= tf:
                reds += len(slot)
        return reds
    elif card == "yellow":
        yellows = 0
        evaluate = ych if team == "home" else yca
        for idx, slot in enumerate(evaluate):
            if idx <= tf:
                yellows += len(slot)
        return yellows


def calc_forward_pass_per_slot(match_id):
    """calculates the forwards passes per timeframe

    Args:
        match_id (int): statsbomb match id for the game

    Returns:
        list, list: forward passes home, away
    """
    fh, sh = get_action_per_timeframe(match_id, "pass")
    game = [fh, sh]
    timeslots_home = [[] for x in range(100)]
    timeslots_away = [[] for x in range(100)]
    for half_idx, half in enumerate(game):
        for idx, slot in enumerate(half):
            for event in slot:
                # pass is not complete
                if "outcome" in event.raw_event["pass"]:
                    continue
                # pass is not towards the goal
                if (
                    event.raw_event["pass"]["end_location"][0]
                    <= event.raw_event["location"][0]
                ):
                    continue
                if event.team.ground.value == "home":
                    timeslots_home[idx + (half_idx * 50)].append(event)
                elif event.team.ground.value == "away":
                    timeslots_away[idx + (half_idx * 50)].append(event)
                else:
                    print("Oh no!")

    return timeslots_home, timeslots_away


def calc_rolling_avg_forward_pass(match_id, tf, team, M=10):
    """calculates the value for the rolling average of forward passes

    Args:
        match_id (int): statsbomb match id
        tf (int): timeframe for the calculation, 0-99
        team (string): home or away
        M (int, optional): Size of rolling average. Defaults to 10.

    Returns:
        float: rolling average over attacking passes
    """
    home, away = calc_forward_pass_per_slot(match_id)
    if team == "home":
        r_avg = get_rolling_avg(home, tf, M)
    elif team == "away":
        r_avg = get_rolling_avg(away, tf, M)
    return r_avg


def calc_rolling_avg_xT(match_id, tf, team, xTmodell, M=12):
    """calculates the value for the rolling average of forward passes

    Args:
        match_id (int): statsbomb match id
        tf (int): timeframe for the calculation, 0-99
        team (string): home or away
        xTmodell ([[]]): the matrix of the xT modell
        M (int, optional): Size of rolling average. Defaults to 12.

    Returns:
        float: rolling average over xT
    """
    home, away = calc_xT_per_slot(match_id, xTmodell)
    for idx in range(len(home)):
        home[idx] = np.sum(home[idx])
        away[idx] = np.sum(away[idx])
    if team == "home":
        r_avg = get_rolling_avg(home, tf, M)
    elif team == "away":
        r_avg = get_rolling_avg(away, tf, M)
    return r_avg


def calc_gso_per_slot(match_id, xG_modell, threshold=0.15):
    """calculate the goal scoring opportunities per timeslot.
       Gso consist of all shots and players in good positions (xG >= threshold)

    Args:
        match_id (int): statsbomb match_id
        xG_modell ([[]]): matrix of xG modell
        threshold (float, optional): Threshold of xG to be considdered a gso. Defaults to 0.15.

    Returns:
        list, list: list of all gso for home, away
    """
    # shots
    fh, sh = get_action_per_timeframe(match_id, "shot")
    game = [fh, sh]
    timeslots_home_shot = [[] for x in range(100)]
    timeslots_away_shot = [[] for x in range(100)]
    for half_idx, half in enumerate(game):
        for idx, slot in enumerate(half):
            for event in slot:
                # dont care if the shot is good or bad, just count it
                if event.team.ground.value == "home":
                    timeslots_home_shot[idx + (half_idx * 50)].append(event)
                elif event.team.ground.value == "away":
                    timeslots_away_shot[idx + (half_idx * 50)].append(event)
                else:
                    print("Oh no!")
    # passes in dangerous positions
    fh, sh = get_action_per_timeframe(match_id, "pass")
    game = [fh, sh]
    timeslots_home_pass = [[] for x in range(100)]
    timeslots_away_pass = [[] for x in range(100)]
    for half_idx, half in enumerate(game):
        for idx, slot in enumerate(half):
            for event in slot:
                if "outcome" in event.raw_event["pass"]:
                    continue
                w, z = get_mat_pos(
                    event.raw_event["pass"]["end_location"][0],
                    event.raw_event["pass"]["end_location"][1],
                )
                xG = xG_modell[z][w]
                if xG >= threshold:
                    if event.team.ground.value == "home":
                        timeslots_home_pass[idx +
                                            (half_idx * 50)].append(event)
                    elif event.team.ground.value == "away":
                        timeslots_away_pass[idx +
                                            (half_idx * 50)].append(event)
                    else:
                        print("Oh no!")
    # carries to dangerous positions
    fh, sh = get_action_per_timeframe(match_id, "carry")
    game = [fh, sh]
    timeslots_home_carry = [[] for x in range(100)]
    timeslots_away_carry = [[] for x in range(100)]
    for half_idx, half in enumerate(game):
        for idx, slot in enumerate(half):
            for event in slot:
                w, z = get_mat_pos(
                    event.raw_event["carry"]["end_location"][0],
                    event.raw_event["carry"]["end_location"][1],
                )
                xG = xG_modell[z][w]
                if xG >= threshold:
                    if event.team.ground.value == "home":
                        timeslots_home_carry[idx +
                                             (half_idx * 50)].append(event)
                    elif event.team.ground.value == "away":
                        timeslots_away_carry[idx +
                                             (half_idx * 50)].append(event)
                    else:
                        print("Oh no!")

    # combine
    timeslots_home = [[] for x in range(100)]
    timeslots_away = [[] for x in range(100)]
    for i in range(100):
        for x in timeslots_home_shot[i]:
            timeslots_home[i].append(x)
        for x in timeslots_away_shot[i]:
            timeslots_away[i].append(x)
        for x in timeslots_home_pass[i]:
            timeslots_home[i].append(x)
        for x in timeslots_away_pass[i]:
            timeslots_away[i].append(x)
        for x in timeslots_home_carry[i]:
            timeslots_home[i].append(x)
        for x in timeslots_away_carry[i]:
            timeslots_away[i].append(x)

    return timeslots_home, timeslots_away


def gso_average(match_id, tf, team, xGmodell):
    """calculate the goal scoring opportunity average for a team

    Args:
        match_id (int): statsbomb match id
        tf (int): timeframe 0-99 for the calculation
        team (string): home or away
        xGmodell ([[]]): matrix of xG modell to use

    Returns:
        float: average of gso for the team
    """
    tsh, tsa = calc_gso_per_slot(match_id, xGmodell)
    if team == "home":
        ts = tsh
    elif team == "away":
        ts = tsa
    else:
        print("Error! Team must be either home or away")
    sum = 0
    for i in range(tf + 1):
        sum += len(ts[i])
    return sum / (tf + 1)


def calc_duel_strength_slots(match_id):
    """calculate the takeons won per timeframe per team and all attempted

    Args:
        match_id (int): statsbomb match id

    Returns:
        list, list, list: list of won takeons home, away and all attempted takeons
    """
    fh, sh = get_action_per_timeframe(match_id, "take_on")
    game = [fh, sh]
    timeslots_home_takeon = [[] for x in range(100)]
    timeslots_away_takeon = [[] for x in range(100)]
    timeslots_all_takeon = [[] for x in range(100)]
    for half_idx, half in enumerate(game):
        for idx, slot in enumerate(half):
            for event in slot:
                won = event.raw_event["dribble"]["outcome"]["name"] == "Complete"
                if event.team.ground.value == "home":
                    timeslots_all_takeon[idx + (half_idx * 50)].append(event)
                    if won:
                        timeslots_home_takeon[idx +
                                              (half_idx * 50)].append(event)
                    else:
                        timeslots_away_takeon[idx +
                                              (half_idx * 50)].append(event)
                elif event.team.ground.value == "away":
                    timeslots_all_takeon[idx + (half_idx * 50)].append(event)
                    if won:
                        timeslots_away_takeon[idx +
                                              (half_idx * 50)].append(event)
                    else:
                        timeslots_home_takeon[idx +
                                              (half_idx * 50)].append(event)
                else:
                    print("Oh no!")

    return timeslots_home_takeon, timeslots_away_takeon, timeslots_all_takeon


def duel_percentage(match_id):
    """get percentage per slot of won takeons

    Args:
        match_id (int): statsbomb match id

    Returns:
        list, list: list of timeslots with won takon percentage home, away
    """
    home, away, all = calc_duel_strength_slots(match_id)
    timeslots_home_duel_won_per = [0 for x in range(100)]
    timeslots_away_duel_won_per = [0 for x in range(100)]
    for x in range(100):
        all_duels = len(all[x])
        if all_duels == 0:
            timeslots_home_duel_won_per[x] = 0.5
            timeslots_away_duel_won_per[x] = 0.5
        else:
            timeslots_home_duel_won_per[x] = len(home[x]) / all_duels
            timeslots_away_duel_won_per[x] = len(away[x]) / all_duels

    return timeslots_home_duel_won_per, timeslots_away_duel_won_per


def get_duel_strength(match_id, frame, team, M=10):
    """get average duel strength for last n timeframes

    Args:
        match_id (int): statsbomb match id
        team (string): home or away
        frame (int): timeframe for computation 0-99
        n_average (int): number of timeframes to look back. Defaults to 10
    Returns:
        float: rolling average over duel strength
    """
    a, b = duel_percentage(match_id)
    use = a if team == "home" else b
    ds = get_rolling_avg(use, frame, M)
    return ds


def get_score_diff_per_game(match_id):
    timeslot_home, timeslot_away = get_goals_per_timeframe(match_id)
    goal_h, goal_a = 0, 0
    goaldiff_h = [0 for x in range(100)]
    goaldiff_a = [0 for x in range(100)]
    for i in range(100):
        goal_h += len(timeslot_home[i])
        goal_a += len(timeslot_away[i])
        goaldiff_h[i] = goal_h - goal_a
        goaldiff_a[i] = goal_a - goal_h
    return goaldiff_h, goaldiff_a


def get_team_goals_per_game(match_id):
    timeslot_home, timeslot_away = get_goals_per_timeframe(match_id)
    gh, ga = 0, 0
    gh_slots, ga_slots = [0 for _ in range(100)], [0 for _ in range(100)]
    for i in range(100):
        gh += len(timeslot_home[i])
        gh_slots[i] = gh
        ga += len(timeslot_away[i])
        ga_slots[i] = ga
    return gh_slots, ga_slots


def get_num_cards_per_game(match_id):
    ych, rch, yca, rca = get_cards_per_timeframe(match_id)
    red_h, red_a = 0, 0
    red_slots_h, red_slots_a = [0 for _ in range(100)], [0 for _ in range(100)]
    yel_h, yel_a = 0, 0
    yel_slots_h, yel_slots_a = [0 for _ in range(100)], [0 for _ in range(100)]
    for i in range(100):
        red_h += len(rch[i])
        red_a += len(rca[i])
        yel_h += len(ych[i])
        yel_a += len(yca[i])
        red_slots_h[i] = red_h - red_a
        red_slots_a[i] = red_a - red_h
        yel_slots_h[i] = yel_h - yel_a
        yel_slots_a[i] = yel_a - yel_h
    return red_slots_h, red_slots_a, yel_slots_h, yel_slots_a


def calc_rolling_avg_forward_pass_per_game(match_id, M=10):
    home, away = calc_forward_pass_per_slot(match_id)
    fwp_h, fwp_a = [0.0 for _ in range(100)], [0.0 for _ in range(100)]
    for i in range(100):
        fwp_h[i] = get_rolling_avg(home, i, M)
        fwp_a[i] = get_rolling_avg(away, i, M)
    return fwp_h, fwp_a


def gso_average_per_game(match_id, xGmodell):
    gso_h, gso_a = calc_gso_per_slot(match_id, xGmodell)
    gso_slots_h, gso_slots_a = [0 for _ in range(100)], [0 for _ in range(100)]
    sum_h, sum_a = 0, 0
    for i in range(100):
        sum_h += len(gso_h[i])
        sum_a += len(gso_a[i])
        gso_slots_h[i] = (sum_h / i) if i > 0 else 0
        gso_slots_a[i] = (sum_a / i) if i > 0 else 0
    return gso_slots_h, gso_slots_a


def calc_rolling_avg_xT_per_game(match_id, xTmodell, M=12):
    home, away = calc_xT_per_slot(match_id, xTmodell)
    xT_h, xT_a = [0 for _ in range(100)], [0 for _ in range(100)]
    for idx in range(100):
        home[idx] = np.sum(home[idx])
        away[idx] = np.sum(away[idx])
    for i in range(100):
        xT_h[i] = get_rolling_avg(home, i, M)
        xT_a[i] = get_rolling_avg(away, i, M)
    return xT_h, xT_a


def get_duel_strength_per_game(match_id, M=10):
    home, away = duel_percentage(match_id)
    ds_h, ds_a = [0 for _ in range(100)], [0 for _ in range(100)]
    for i in range(100):
        ds_h[i] = get_rolling_avg(home, i, M)
        ds_a[i] = get_rolling_avg(away, i, M)
    return ds_h, ds_a


def get_model_training_data(match_id, frame, team):
    # percantage of gametime completed
    # frame 0-99 ^= gamepercentage 1-100%
    gt = frame + 1
    # score differential
    sd = get_score_diff_at_tf(match_id, frame, team)
    # team goals
    tg = get_team_goals(match_id, frame, team)
    # red cards
    rc = get_num_cards(match_id, "red", frame, team)
    # yellow cards
    yc = get_num_cards(match_id, "yellow", frame, team)
    # goals scoring opportunities
    with open("/home/morten/Develop/Live-Win-Prob/models/simple_xG", "rb") as fp:
        xGmodell = pickle.load(fp)
    gco = gso_average(match_id, frame, team, xGmodell)
    # attacking passes
    ap = calc_rolling_avg_forward_pass(match_id, frame, team)
    # expected Thread
    with open("/home/morten/Develop/Live-Win-Prob/models/xT", "rb") as fp:
        xTmodell = pickle.load(fp)
    xT = calc_rolling_avg_xT(match_id, frame, team, xTmodell)
    # duel strength
    ds = get_duel_strength(match_id, frame, team)

    return gt, sd, tg, rc, yc, gco, ap, xT, ds


def get_model_training_data_per_game(match_id):
    # score differential
    sd_h, sd_a = get_score_diff_per_game(match_id)
    # team goals
    tg_h, tg_a = get_team_goals_per_game(match_id)
    # red / yellow cards
    rc_h, rc_a, yel_h, yel_a = get_num_cards_per_game(match_id)
    # goals scoring opportunities
    with open("/home/morten/Develop/Live-Win-Prob/models/statsbomb_xG", "rb") as fp:
        xGmodell = pickle.load(fp)
    gso_h, gso_a = gso_average_per_game(match_id, xGmodell)
    # attacking passes
    fwp_h, fwp_a = calc_rolling_avg_forward_pass_per_game(match_id)
    # expected Thread
    with open("/home/morten/Develop/Live-Win-Prob/models/statsbomb_xT", "rb") as fp:
        xTmodell = pickle.load(fp)
    xT_h, xT_a = calc_rolling_avg_xT_per_game(match_id, xTmodell)
    # duel strength
    ds_h, ds_a = get_duel_strength_per_game(match_id)

    return (
        [sd_h, sd_a],
        [tg_h, tg_a],
        [rc_h, rc_a],
        [yel_h, yel_a],
        [gso_h, gso_a],
        [fwp_h, fwp_a],
        [xT_h, xT_a],
        [ds_h, ds_a],
    )
