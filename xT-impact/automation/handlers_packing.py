import os
import sys
sys.path.append("/home/morten/Develop/packing-report/xT-impact/")
from proto_files.python.games import Schedule, ScheduleGame
from proto_files.python.lineups import LineupList, LineupTeam, Lineup
from proto_files.python.table import TableList, TableCompetition, TableTeam
from proto_files.python.eval import BetList, Evaluations, Bet, Eval

from global_packing import init_logging
import pandas as pd
import numpy as np

from typing import List

class TableHandler:
    logger = init_logging()
    table_list = TableList()
    def __init__(self):
        if "tables.pb" in os.listdir("/home/morten/Develop/packing-report/xT-impact/automation/database"):
            self.table_list = TableList().parse(open(f"/home/morten/Develop/packing-report/xT-impact/automation/database/tables.pb", "rb").read())
        else:
            self.table_list = TableList()
            self.logger.info("Created empty Tables file")

    def _add_competition(self, league):
        available_comps = pd.DataFrame(self.table_list.tables)
        if available_comps.empty or league not in available_comps.competition.values:
            table = TableCompetition()
            table.competition = league
            self.table_list.tables.append(table)
            self.logger.info(f"Inserted new competition {league} into tables")

    def _update_team_entry(self, team, home, goals_for, goals_against):
        home_goals = goals_for if home else goals_against
        away_goals = goals_against if home else goals_for
        team.num_games += 1
        team.points += (
            3
            if goals_for > goals_against
            else 1
            if goals_for == goals_against
            else 0
        )
        team.form_goals_for.append(home_goals)
        team.form_goals_against.append(away_goals)
        if home:
            team.points_home += (
                3
                if home_goals > away_goals
                else 1
                if home_goals == away_goals
                else 0
            )
            team.points_away += 0
            team.form_goals_for_home.append(home_goals)
            team.form_goals_against_home.append(away_goals) 
        else:
            team.points_home += 0
            team.points_away = (
                3
                if away_goals > home_goals
                else 1
                if home_goals == away_goals
                else 0
            )
            team.form_goals_for_away.append(away_goals)
            team.form_goals_against_away.append(home_goals)
        self.logger.info(f"Updated table team entry for team {team.team_name}")

    def update_table(self, league, team_id, team_name, home, goals_for, goals_against):
        self._add_competition(league)
        for table in self.table_list.tables:
            if table.competition == league:
                table_df = pd.DataFrame(table.table_teams)
                if table_df.empty or team_id not in table_df.team_id.values:
                    team = TableTeam()
                    team.team_id = team_id
                    team.team_name = team_name
                    self._update_team_entry(team, home, goals_for, goals_against)
                    table.table_teams.append(team)
                    self.logger.info(f"Team {team_name} not in table, inserting it")
                else:
                    for team in table.table_teams:
                        if team.team_id == team_id:
                            self._update_team_entry(team, home, goals_for, goals_against)
    
    def get_table_info(self, team, opp, league, home):
        table_dict = {}
        for table in self.table_list.tables:
            if table.competition == league:
                table_df = pd.DataFrame(table.table_teams).sort_values("points").reset_index()
                # TODO table information
                table_dict["team_table_pos"] = 1
                table_dict["opp_table_pos"] = 1
                table_dict["team_home_away_table_pos"] = 1
                table_dict["opp_home_away_table_pos"] = 1
                ###
                table_dict["team_form_for"] = np.sum(
                    table_df[table_df["team_id"] == team].form_goals_for.values[0][-5:]
                )
                table_dict["team_form_against"] = np.sum(
                    table_df[table_df["team_id"] == team].form_goals_against.values[0][-5:]
                )
                table_dict["opp_form_for"] = np.sum(
                    table_df[table_df["team_id"] == opp].form_goals_for.values[0][-5:]
                )
                table_dict["opp_form_against"] = np.sum(
                    table_df[table_df["team_id"] == opp].form_goals_against.values[0][-5:]
                )

                table_dict["team_home_away_form_for"] = (
                    np.sum(
                        table_df[table_df["team_id"] == team].form_goals_for_home.values[0][
                            -5:
                        ]
                    )
                    if home
                    else np.sum(
                        table_df[table_df["team_id"] == team].form_goals_for_away.values[0][
                            -5:
                        ]
                    )
                )
                table_dict["opp_home_away_form_for"] = (
                    np.sum(
                        table_df[table_df["team_id"] == opp].form_goals_for_home.values[0][
                            -5:
                        ]
                    )
                    if not home
                    else np.sum(
                        table_df[table_df["team_id"] == opp].form_goals_for_away.values[0][
                            -5:
                        ]
                    )
                )
                table_dict["team_home_away_form_against"] = (
                    np.sum(
                        table_df[
                            table_df["team_id"] == team
                        ].form_goals_against_home.values[0][-5:]
                    )
                    if home
                    else np.sum(
                        table_df[
                            table_df["team_id"] == team
                        ].form_goals_against_away.values[0][-5:]
                    )
                )
                table_dict["opp_home_away_form_against"] = (
                    np.sum(
                        table_df[table_df["team_id"] == opp].form_goals_against_home.values[
                            0
                        ][-5:]
                    )
                    if not home
                    else np.sum(
                        table_df[table_df["team_id"] == opp].form_goals_against_away.values[
                            0
                        ][-5:]
                    )
                )

        return table_dict

    def write_table(self):
        with open(f"/home/morten/Develop/packing-report/xT-impact/automation/database/tables.pb", "wb") as f:
            f.write(bytes(self.table_list))
##############################################################################################################
class LineupHandler:
    logger = init_logging()
    lineup_list = LineupList()
    def __init__(self):
        if "lineups.pb" in os.listdir("/home/morten/Develop/packing-report/xT-impact/automation/database/"):
            self.lineup_list = LineupList().parse(open(f"/home/morten/Develop/packing-report/xT-impact/automation/database/lineups.pb", "rb").read())
        else:
            self.lineup_list = LineupList()
            self.logger.info("Created empty Lineups file")
    
    def add_lineup(self, team_name, df_players):
        df_lineup_list = pd.DataFrame(self.lineup_list.teams)
        if df_lineup_list.empty or team_name not in df_lineup_list.team_name.values:
            team = LineupTeam()
            team.team_name = team_name
            team.last_starting_11 = self._create_lineup(team_name, df_players)
            self.lineup_list.teams.append(team)
            self.logger.info(f"added new team {team_name} to lineups")
        else:
            for t in self.lineup_list.teams:
                if t.team_name == team_name:
                    t.last_starting_11 = self._create_lineup(team_name, df_players)
                    self.logger.info(f"Updated team {team_name} in lineups")
        
    def _create_lineup(self, team_name, df_players):
        line_up = Lineup()
        df_lineup = df_players.loc[
            (df_players["team_name"] == team_name) & (df_players["is_starter"])
        ]
        for _, player in df_lineup.iterrows():
            line_up.players_id.append(player.player_id)
        return line_up

    def get_lineup(self, team_name):
        for t in self.lineup_list.teams:
            if t.team_name == team_name:
                return True, t.last_starting_11.players_id
        self.logger.error(f"Team {team_name} not found")
        return False, [[]]

    def write_lineup(self):
        with open(f"/home/morten/Develop/packing-report/xT-impact/automation/database/lineups.pb", "wb") as f:
            f.write(bytes(self.lineup_list))
##############################################################################################################

class ScheduleHandler:
    logger = init_logging()
    next_games = Schedule()
    past_games = Schedule()
    def __init__(self):
        database_files = os.listdir("/home/morten/Develop/packing-report/xT-impact/automation/database/")
        if "next_games.pb" not in database_files:
            self.next_games = Schedule()
            self.logger.info("Created empty next games files")
        else:
            self.next_games = Schedule().parse(open(f"/home/morten/Develop/packing-report/xT-impact/automation/database/next_games.pb", "rb").read())
        if "past_games.pb" not in database_files:
            self.past_games = Schedule()
            self.logger.info("Created empty past games files")
        else:
            self.past_games = Schedule().parse(open(f"/home/morten/Develop/packing-report/xT-impact/automation/database/past_games.pb", "rb").read())
    
    def add_game(self, schedule_line, next_or_past):
        schedule = self.next_games if next_or_past == "n" else self.past_games
        if pd.DataFrame(schedule.games).empty or schedule_line.game_id not in pd.DataFrame(schedule.games).game_id.values:
            game = ScheduleGame()
            game.game_id = schedule_line.game_id
            game.game_date = str(schedule_line.date)
            game.home_team = schedule_line.home_team
            game.away_team = schedule_line.away_team
            game.league = schedule_line.league_name
            schedule.games.append(game)
            self.logger.info(f"Added game with id {game.game_id} to {next_or_past} games list")
        else:
            self.logger.info(
                f"Skipped game with id {schedule_line.game_id} as it was already in the {next_or_past} list"
            )
    def add_game_by_game(self, game, next_or_past):
        schedule = self.next_games if next_or_past == "n" else self.past_games
        schedule.games.append(game)

    def remove_game_by_game(self, game, next_or_past):
        schedule = self.next_games if next_or_past == "n" else self.past_games
        schedule.games.remove(game)

    def get_schedule(self, next_or_past):
        schedule = self.next_games if next_or_past == "n" else self.past_games
        return schedule

    def write_schedule(self, next_or_past):
        schedule = self.next_games if next_or_past == "n" else self.past_games
        file_name = "next_games.pb" if next_or_past == "n" else "past_games.pb"
        with open(f"/home/morten/Develop/packing-report/xT-impact/automation/database/"+file_name, "wb") as f:
            f.write(bytes(schedule))
##############################################################################################################


class PlayerHandler:
    pass


class EvalHandler:
    logger = init_logging()
    bet_list = BetList()
    evaluations = Evaluations()
    def __init__(self):
        database_files = os.listdir("/home/morten/Develop/packing-report/xT-impact/automation/database/")
        if "evaluations.pb" not in database_files:
            self.evaluations = Evaluations()
            self.logger.info("Created empty evaluations file")
        else:
            self.evaluations = Evaluations().parse(open(f"/home/morten/Develop/packing-report/xT-impact/automation/database/evaluations.pb", "rb").read())
        if "bets.pb" not in database_files:
            self.bet_list = BetList()
            self.logger.info("Created empty bet list file")
        else:
            self.bet_list = BetList().parse(open(f"/home/morten/Develop/packing-report/xT-impact/automation/database/bets.pb", "rb").read())
    
    def add_bet(self, g_id:int, home: bool, draw: bool, away: bool, odds: List[float]):
        bet = Bet()
        bet.bet_home = home
        bet.bet_draw = draw
        bet.bet_away = away
        bet.game_id = g_id 
        bet.home_odd = odds[0]
        bet.draw_odd = odds[1]
        bet.away_odd = odds[2]
        self.bet_list.bets.append(bet)
        self.logger.info(f"Added id {g_id} bet list")

    def remove_bet(self, g_id):
        for bet in self.bet_list.bets:
            if bet.game_id == g_id:
                self.bet_list.bets.remove(bet)
                self.logger.info(f"Removed id {g_id} bet list")

    def get_bet(self, g_id):
        for bet in self.bet_list.bets:
            if g_id == bet.game_id:
                return bet
        return None

    def write_bets(self):
        with open(f"/home/morten/Develop/packing-report/xT-impact/automation/database/bets.pb", "wb") as f:
            f.write(bytes(self.bet_list))

    def update_eval(self, result_hda, bet_hda, odds_hda):
        einsatz = 1
        for update in [self.evaluations.all_time_evaluation, self.evaluations.week_evaluation, self.evaluations.month_evaluation]:
            update.num_games += 1
            if any(bet_hda):
                if bet_hda[0]:
                    update.num_bets += 1
                    update.num_bets_home += 1
                    if result_hda == 0:
                        update.num_bets_home_won += 1
                        update.money_won_home += ((einsatz * odds_hda[0]) - einsatz)
                        update.money_won += ((einsatz * odds_hda[0]) - einsatz)
                    else:
                        update.money_won_home += (-einsatz)
                        update.money_won += (-einsatz)
            if bet_hda[1]:
                    update.num_bets += 1
                    update.num_bets_draw += 1
                    if result_hda == 1:
                        update.num_bets_draw_won += 1
                        update.money_won_draw += ((einsatz * odds_hda[1]) - einsatz)
                        update.money_won += ((einsatz * odds_hda[1]) - einsatz)
                    else:
                        update.money_won_draw += (-einsatz)
                        update.money_won += (-einsatz)
            if bet_hda[2]:
                    update.num_bets += 1
                    update.num_bets_away += 1
                    if result_hda == 2:
                        update.num_bets_away_won += 1
                        update.money_won_away += ((einsatz * odds_hda[2]) - einsatz)
                        update.money_won += ((einsatz * odds_hda[2]) - einsatz)
                    else:
                        update.money_won_away += (-einsatz)
                        update.money_won += (-einsatz)

    def get_eval(self):
        return self.evaluations

    def reset_week(self):
        self.evaluations.week_evaluation = Eval()
        self.logger.info(f"Reset weekly eval")

    def reset_month(self):
        self.evaluations.month_evaluation = Eval()
        self.logger.info(f"Reset monthly eval")

    def write_eval(self):
        with open(f"/home/morten/Develop/packing-report/xT-impact/automation/database/evaluations.pb", "wb") as f:
            f.write(bytes(self.evaluations))