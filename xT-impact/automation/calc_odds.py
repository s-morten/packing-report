#!/usr/bin/python

from global_packing import init_logging, get_xT_modell, LEAGUE_LIST
import soccerdata as sd
from datetime import datetime, timedelta
import os
import sys
sys.path.append('/home/morten/Develop/packing-report/xT-impact/')
from proto_files.python.games import Schedule, ScheduleGame
from proto_files.python.player import Player, Game
from proto_files.python.lineups import LineupList
from handlers_packing import LineupHandler

import pandas as pd

import socceraction.spadl as spadl
import socceraction.xthreat as xthreat
import numpy as np
import math
from pymc_model import Poisson_Prediction_Model
sys.path.append("/home/morten/Develop/packing-report/OddsToPercentage/")
from oddCalculation import OddToPercentage
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import soccerdata as sd
import pandas as pd
from pathlib import PosixPath
from soccerapi.api import Api888Sport
import json
from handlers_packing import ScheduleHandler, EvalHandler

def get_bookie_oods(home, away, league):
    league_dict = {"GER-Bundesliga": "https://www.888sport.com/#/filter/football/germany/bundesliga/", 
                    "GER-Bundesliga2": 'https://www.888sport.com/#/filter/football/germany/2__bundesliga/',
                    "ENG-Premier League": 'https://www.888sport.com/#/filter/football/england/premier_league/',
                    "FRA-Ligue 1": "https://www.888sport.com/#/filter/football/france/ligue_1/",
                    "ESP-La Liga": "https://www.888sport.com/#/filter/football/spain/la_liga/",
                    "ITA-Serie A": "https://www.888sport.com/#/filter/football/italy/serie_a/"
                }
    api = Api888Sport()
    url = league_dict[league]
    odds = api.odds(url)
    df = pd.json_normalize(odds)
    name_substitutes = json.load(open("/home/morten/soccerdata/config/teamname_replacements.json"))
    for replace in name_substitutes:
        for name in name_substitutes[replace]:
            df.replace(name, replace, inplace=True)
    df = df.loc[(df["home_team"] == home) & (df["away_team"] == away)]
    h_odds, d_odds, a_odds =  df["full_time_result.1"].values[0],df["full_time_result.X"].values[0],df["full_time_result.2"].values[0]
    o2p = OddToPercentage()
    home_prob, home_perc = o2p.odd_to_percentage(h_odds)
    draw_prob, draw_perc = o2p.odd_to_percentage(d_odds)
    away_prob, away_perc = o2p.odd_to_percentage(a_odds)
    # make them fair
    bookie_sum = home_prob + draw_prob + away_prob
    home_perc = home_perc / bookie_sum
    draw_perc = draw_perc / bookie_sum
    away_perc = away_perc / bookie_sum

    return [home_perc, draw_perc, away_perc, h_odds, d_odds, a_odds]

def most_common(lst):
    return max(set(lst), key=lst.count)

def create_prediction_data(next_games_df, logger):
    data_frames = []
    successfull = []
    failed, skipped, skipped_at_beginning = 0, 0, 0
    lineup_handler = LineupHandler()
    for idx, (_, game_row) in enumerate(next_games_df.iterrows()):
        home_team = game_row.home_team
        away_team = game_row.away_team
        game_date = game_row.game_date
        # TODO what if no s11 is foud, shouldnt be possible
        success_h, h_s11 = lineup_handler.get_lineup(home_team)
        success_a, a_s11 = lineup_handler.get_lineup(away_team)
        if not (success_h and success_a):
            continue
        data = {"home": {'starter': {"xg_for": 0., "xt_all": 0., "xt_only_pos": 0., "xd_press": 0., "xd_normal": 0., "xk": 0., "gi": 0., "xg_against": 0., "xt_against_all": 0., "xt_against_only_pos": 0.},
                        'subs': {"xg_for": 0., "xt_all": 0., "xt_only_pos": 0., "xd_press": 0., "xd_normal": 0., "xk": 0., "gi": 0., "xg_against": 0., "xt_against_all": 0., "xt_against_only_pos": 0.}},
                "away": {'starter': {"xg_for": 0., "xt_all": 0., "xt_only_pos": 0., "xd_press": 0., "xd_normal": 0., "xk": 0., "gi": 0., "xg_against": 0., "xt_against_all": 0., "xt_against_only_pos": 0.},
                        'subs': {"xg_for": 0., "xt_all": 0., "xt_only_pos": 0., "xd_press": 0., "xd_normal": 0., "xk": 0., "gi": 0., "xg_against": 0., "xt_against_all": 0., "xt_against_only_pos": 0.}},
                "general": {"game_id": set(), "table_pos_home": set(), "table_pos_away": set(), "ha_table_pos_home": set(), "ha_table_pos_away": set(), 
                            "form_home_for": set(), "form_home_against": set(), "form_away_for": set(), "form_away_against": set(), "ha_form_home_for": set(), 
                            "ha_form_home_against": set(), "ha_form_away_for": set(),  "ha_form_away_against": set(), "elo_home": set(), "elo_away": set()}}
        starter_home_empty, starter_away_empty = 0, 0
        for player_id, is_home in zip(np.concatenate([h_s11, a_s11]), np.concatenate([[True for _ in range(11)],[False for _ in range(11)]])):
            proto_player = Player().parse(open(f"/home/morten/Develop/packing-report/xT-impact/data/data_0.31/{str(player_id)}.pb", "rb").read())
            player_df = pd.DataFrame(proto_player.expected_game_impact)
            player_df.drop_duplicates(inplace=True)
            player_df = player_df.sort_values("game_date").reset_index(drop=True)
            # game_df = player_df[player_df["game_date"] == game_date]
            # previous_df = player_df[player_df["game_date"] < game_date]
            # previous_df = previous_df.loc[(previous_df["starter"] == game_df["starter"].values[0]) & (previous_df["home"] == game_df["home"].values[0])]
            previous_df = player_df.loc[(player_df["starter"] == True) & (player_df["home"] == is_home)]
            previous_df = previous_df[-5:]
            is_starter = "starter" # if game_df["starter"].values[0] else "subs"

            if previous_df.empty:
                if is_home:
                    starter_home_empty += 1
                else:
                    starter_away_empty += 1
                continue
            home_bool = is_home
            if is_home:
                is_home = 'home'
            else:
                is_home = 'away'
            data[is_home][is_starter]["xg_for"] += (np.mean((previous_df["xg"] / previous_df["minutes_played"])) * 90) if not math.isnan((np.mean((previous_df["xg"] / previous_df["minutes_played"])) * 90)) else 0
            data[is_home][is_starter]["xt_all"] += (np.mean((previous_df["xt_all"] / previous_df["minutes_played"])) * 90) if not math.isnan((np.mean((previous_df["xt_all"] / previous_df["minutes_played"])) * 90)) else 0
            data[is_home][is_starter]["xt_only_pos"] += (np.mean((previous_df["xt_only_pos"] / previous_df["minutes_played"])) * 90) if not math.isnan((np.mean((previous_df["xt_only_pos"] / previous_df["minutes_played"])) * 90)) else 0
            data[is_home][is_starter]["xd_press"] += (np.mean((previous_df["xd_press"] / previous_df["minutes_played"])) * 90) if not math.isnan((np.mean((previous_df["xd_press"] / previous_df["minutes_played"])) * 90)) else 0
            data[is_home][is_starter]["xd_normal"] += (np.mean((previous_df["xd_def"] / previous_df["minutes_played"])) * 90) if not math.isnan((np.mean((previous_df["xd_def"] / previous_df["minutes_played"])) * 90)) else 0
            data[is_home][is_starter]["xk"] += (np.mean((previous_df["xk_save"] / previous_df["minutes_played"])) * 90) if not math.isnan((np.mean((previous_df["xk_save"] / previous_df["minutes_played"])) * 90)) else 0
            data[is_home][is_starter]["gi"] += (np.mean((previous_df["gi"] / previous_df["minutes_played"])) * 90) if not math.isnan((np.mean((previous_df["gi"] / previous_df["minutes_played"])) * 90)) else 0
            data[is_home][is_starter]["xg_against"] += (np.mean((previous_df["xg_against"] / previous_df["minutes_played"])) * 90) if not math.isnan((np.mean((previous_df["xg_against"] / previous_df["minutes_played"])) * 90)) else 0
            data[is_home][is_starter]["xt_against_all"] += (np.mean((previous_df["xt_against_all"] / previous_df["minutes_played"])) * 90) if not math.isnan((np.mean((previous_df["xt_against_all"] / previous_df["minutes_played"])) * 90)) else 0
            data[is_home][is_starter]["xt_against_only_pos"] += (np.mean((previous_df["xt_against_only_pos"] / previous_df["minutes_played"])) * 90) if not math.isnan((np.mean((previous_df["xt_against_only_pos"] / previous_df["minutes_played"])) * 90)) else 0

            last_game_df = previous_df.tail(1)
            data['general']["game_id"].add(game_row['game_id'])
            if home_bool:
                data["general"]["table_pos_home"].add(last_game_df["team_pos"].values[0])
                data["general"]["ha_table_pos_home"].add(last_game_df["team_pos_home_away"].values[0])
                data["general"]["form_home_for"].add(last_game_df["team_form_for"].values[0])
                data["general"]["form_home_against"].add(last_game_df["team_form_against"].values[0])
                data["general"]["ha_form_home_for"].add(last_game_df["team_form_home_away_for"].values[0])
                data["general"]["ha_form_home_against"].add(last_game_df["team_form_home_away_against"].values[0])

            else:
                data["general"]["table_pos_away"].add(last_game_df["opp_position"].values[0])
                data["general"]["ha_table_pos_away"].add(last_game_df["opp_position_home_away"].values[0])
                data["general"]["form_away_for"].add(last_game_df["opp_form_for"].values[0])
                data["general"]["form_away_against"].add(last_game_df["opp_form_against"].values[0])
                data["general"]["ha_form_away_for"].add(last_game_df["opp_form_home_away_for"].values[0])
                data["general"]["ha_form_away_against"].add(last_game_df["opp_form_home_away_against"].values[0])
            
            ce = sd.ClubElo(
                no_cache=False,
                no_store=False,
                data_dir=PosixPath("/home/morten/Develop/Open-Data/soccerdata"),
            )
            ce_df = ce.read_by_date(game_date[:10])
            data["general"]["elo_home"].add(ce_df.loc[home_team].elo)
            data["general"]["elo_away"].add(ce_df.loc[away_team].elo)

        if starter_home_empty > 3 or starter_away_empty > 3:
            skipped += 1
            continue
        df = pd.DataFrame({
            "game_id": [list(data['general']["game_id"])[0]],
            "table_pos_home": [most_common(list(data["general"]["table_pos_home"]))],
            "table_pos_away": [most_common(list(data["general"]["table_pos_away"]))],
            "ha_table_pos_home": [most_common(list(data["general"]["ha_table_pos_home"]))],
            "ha_table_pos_away": [most_common(list(data["general"]["ha_table_pos_away"]))],
            "form_home_for": [most_common(list(data["general"]["form_home_for"]))],
            "form_home_against": [most_common(list(data["general"]["form_home_against"]))],
            "form_away_for": [most_common(list(data["general"]["form_away_for"]))],
            "form_away_against": [most_common(list(data["general"]["form_away_against"]))],
            "ha_form_home_for": [most_common(list(data["general"]["ha_form_home_for"]))],
            "ha_form_home_against": [most_common(list(data["general"]["ha_form_home_against"]))],
            "ha_form_away_for": [most_common(list(data["general"]["ha_form_away_for"]))],
            "ha_form_away_against": [most_common(list(data["general"]["ha_form_away_against"]))],
            "elo_home": [list(data["general"]["elo_home"])[0]],
            "elo_away": [list(data["general"]["elo_away"])[0]],

            "home_xG": [data["home"]["starter"]["xg_for"]], 
            "home_xT_all": [data["home"]["starter"]["xt_all"]],
            "home_xT_only_pos": [data["home"]["starter"]["xt_only_pos"]],
            "home_xD_press": [data["home"]["starter"]["xd_press"]],
            "home_xD_normal": [data["home"]["starter"]["xd_normal"]],
            "home_xK": [data["home"]["starter"]["xk"]],
            "home_gi": [data["home"]["starter"]["gi"]],
            "home_xg_against": [data["home"]["starter"]["xg_against"]],
            "home_xt_all_against": [data["home"]["starter"]["xt_against_all"]],
            "home_xt_only_pos_against": [data["home"]["starter"]["xt_against_only_pos"]],
            "home_sub_xG": [data["home"]["subs"]["xg_for"]], 
            "home_sub_xT_all": [data["home"]["subs"]["xt_all"]],
            "home_sub_xT_only_pos": [data["home"]["subs"]["xt_only_pos"]],
            "home_sub_xD_press": [data["home"]["subs"]["xd_press"]],
            "home_sub_xD_normal": [data["home"]["subs"]["xd_normal"]],
            "home_sub_xK": [data["home"]["subs"]["xk"]],
            "home_sub_gi": [data["home"]["subs"]["gi"]],
            "home_sub_xg_against": [data["home"]["subs"]["xg_against"]],
            "home_sub_xt_all_against": [data["home"]["subs"]["xt_against_all"]],
            "home_sub_xt_only_pos_against": [data["home"]["subs"]["xt_against_only_pos"]],

            "away_xG": [data["away"]["starter"]["xg_for"]], 
            "away_xT_all": [data["away"]["starter"]["xt_all"]],
            "away_xT_only_pos": [data["away"]["starter"]["xt_only_pos"]],
            "away_xD_press": [data["away"]["starter"]["xd_press"]],
            "away_xD_normal": [data["away"]["starter"]["xd_normal"]],
            "away_xK": [data["away"]["starter"]["xk"]],
            "away_gi": [data["away"]["starter"]["gi"]],
            "away_xg_against": [data["away"]["starter"]["xg_against"]],
            "away_xt_all_against": [data["away"]["starter"]["xt_against_all"]],
            "away_xt_only_pos_against": [data["away"]["starter"]["xt_against_only_pos"]],
            "away_sub_xG": [data["away"]["subs"]["xg_for"]], 
            "away_sub_xT_all": [data["away"]["subs"]["xt_all"]],
            "away_sub_xT_only_pos": [data["away"]["subs"]["xt_only_pos"]],
            "away_sub_xD_press": [data["away"]["subs"]["xd_press"]],
            "away_sub_xD_normal": [data["away"]["subs"]["xd_normal"]],
            "away_sub_xK": [data["away"]["subs"]["xk"]],
            "away_sub_gi": [data["away"]["subs"]["gi"]],
            "away_sub_xg_against": [data["away"]["subs"]["xg_against"]],
            "away_sub_xt_all_against": [data["away"]["subs"]["xt_against_all"]],
            "away_sub_xt_only_pos_against": [data["away"]["subs"]["xt_against_only_pos"]]
            })
        data_frames.append(df)
        successfull.append(next_games_df["game_id"].values[0])

    return successfull, pd.concat(data_frames)

def sendMail(subject, text):

    senderEmail = "mortenstehr@hotmail.de"
    empfangsEmail = "mortensportwetten@gmail.com"
    msg = MIMEMultipart()
    msg["From"] = senderEmail
    msg["To"] = empfangsEmail
    msg["Subject"] = subject
    sender_pass = json.load(open("/home/morten/Develop/packing-report/xT-impact/automation/mail-secret.json", "r"))["password"]
    emailText = text
    msg.attach(MIMEText(emailText, "plain"))

    server = smtplib.SMTP("smtp.office365.com", 587)  # Die Server Daten
    server.starttls()
    server.login(
        senderEmail,
        sender_pass
    )  # Das Passwort
    text = msg.as_string()
    server.sendmail(senderEmail, empfangsEmail, text)
    server.quit()

def calc_odds():
    logger = init_logging()
    time_now = datetime.now()
    next_hour = time_now + timedelta(hours=1)
    next_hour = next_hour.strftime('%Y-%m-%d %H:%M:%S')
    # next_hour = "2023-02-02 20:15:00"
    schedule_handler = ScheduleHandler()
    next_games = schedule_handler.get_schedule("n")
    next_games_df = pd.DataFrame(next_games.games)
    if next_games_df.empty:
        logger.info("Next games file is empty. Abort")
        return 
    next_games_df = next_games_df[next_games_df["game_date"] <= next_hour]
    logger.info(f"Found {next_games_df.shape[0]} games in the next hour")
    if next_games_df.empty:
        return
    succ, p_data = create_prediction_data(next_games_df, logger)

    ppm = Poisson_Prediction_Model()
    quotes = ppm.predict(p_data)
    eval_handler = EvalHandler()
    next_games_df = next_games_df.reset_index()
    next_games_df_with_failed = next_games_df.copy(deep=True)
    next_games_df = next_games_df[next_games_df["game_id"].isin(succ)]
    for idx, (_, game) in enumerate(next_games_df.iterrows()):
        h_bet = False
        d_bet = False
        a_bet = False
        telegram_s = ""
        # get betting odds
        bo = get_bookie_oods(game.home_team, game.away_team, game.league)
        # compare odds
        if (quotes[idx][0]*100) - bo[0] > 10:
            telegram_s += f"Bet on {game.home_team}\n"
            h_bet = True
        if (quotes[idx][1]*100) - bo[1] > 10:
            telegram_s += f"Bet on draw\n"
            d_bet = True
        if (quotes[idx][2]*100) - bo[2] > 10:
            telegram_s += f"Bet on {game.away_team}\n"
            a_bet = True
        if (quotes[idx][0]*100) > 60:
            telegram_s += f"Bet on {game.home_team}\n"
            h_bet = True
        if (quotes[idx][1]*100) > 60:
            telegram_s += f"Bet on draw\n"
            d_bet = True
        if (quotes[idx][2]*100) > 60:
            telegram_s += f"Bet on {game.away_team}\n"
            a_bet = True

        eval_handler.add_bet(int(game.game_id), h_bet, d_bet, a_bet, bo[3:])
        if telegram_s != "":
            telegram_s += f"{game.home_team}:{game.away_team}\n"
            telegram_s += f"Model: {round(quotes[idx][0]*100)}-{round(quotes[idx][1]*100)}-{round(quotes[idx][2]*100)}\n"
            telegram_s += f"Bookie: {round(bo[0])}-{round(bo[1])}-{round(bo[2])}\n"
            subject = f"{game.home_team}:{game.away_team}"
            logger.info(telegram_s)
            # sendMail(subject, telegram_s)

    for idx, game in next_games_df_with_failed.reset_index().iterrows():
        for ng in next_games.games:
            if ng.game_id == game.game_id:
                schedule_handler.remove_game_by_game(ng, "n")
                schedule_handler.add_game_by_game(ng, "p")

    schedule_handler.write_schedule("n")
    schedule_handler.write_schedule("p")
    eval_handler.write_bets()

if __name__ == "__main__":
    calc_odds()