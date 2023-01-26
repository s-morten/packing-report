import os
import sys
sys.path.append("/home/morten/Develop/packing-report/xT-impact/")
from proto_files.games import GameList, Game
from proto_files.lineups import TeamList, Lineup
from proto_files.lineups import Team as Team_lineup
from proto_files.table import TableList, Team, Table

from global_packing import init_logging
import pandas as pd
import numpy as np

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
            table = Table()
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
                table_df = pd.DataFrame(table.team)
                if table_df.empty or team_id not in table_df.team_id.values:
                    team = Team()
                    team.team_id = team_id
                    team.team_name = team_name
                    self._update_team_entry(team, home, goals_for, goals_against)
                    table.team.append(team)
                    self.logger.info(f"Team {team_name} not in table, inserting it")
                else:
                    for team in table.team:
                        if team.team_id == team_id:
                            self._update_team_entry(team, home, goals_for, goals_against)
    
    def get_table_info(self, team, opp, league, home):
        table_dict = {}
        for table in self.table_list.tables:
            if table.competition == league:
                print(pd.DataFrame(table.team))
                table_df = pd.DataFrame(table.team).sort_values("points").reset_index()
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
    lineup_list = TeamList()
    def __init__(self):
        if "lineups.pb" in os.listdir("/home/morten/Develop/packing-report/xT-impact/automation/database/"):
            self.lineup_list = TeamList().parse(open(f"/home/morten/Develop/packing-report/xT-impact/automation/database/lineups.pb", "rb").read())
            self.logger.info("Created empty Lineups file")
        else:
            self.lineup_list = TeamList()
    
    def add_lineup(self, team_name, df_players):
        df_lineup_list = pd.DataFrame(self.lineup_list.teams)
        if df_lineup_list.empty or team_name not in df_lineup_list.team_name.values:
            team = Team_lineup()
            team.team_name = team_name
            team.last_starting_11 = self._create_lineup(team_name, df_players)
            self.lineup_list.teams.append(team)
        else:
            for t in self.lineup_list.teams:
                if t.team_name == team_name:
                    t.last_starting_11 = self._create_lineup(team_name, df_players)
        
    def _create_lineup(self, team_name, df_players):
        line_up = Lineup()
        df_lineup = df_players.loc[
            (df_players["team_name"] == team_name) & (df_players["is_starter"])
        ]
        for _, player in df_lineup.iterrows():
            line_up.player_id.append(player.player_id)
        return line_up

    def write_lineup(self):
        with open(f"/home/morten/Develop/packing-report/xT-impact/automation/database/lineups.pb", "wb") as f:
            f.write(bytes(self.lineup_list))
##############################################################################################################

class ScheduleHandler:
    logger = init_logging()
    next_games = GameList()
    past_games = GameList()
    def __init__(self):
        database_files = os.listdir("/home/morten/Develop/packing-report/xT-impact/automation/database/")
        if "next_games.pb" not in database_files:
            self.next_games = GameList()
            self.logger.info("Created empty next games files")
        else:
            self.next_games = GameList().parse(open(f"/home/morten/Develop/packing-report/xT-impact/automation/database/next_games.pb", "rb").read())
        if "past_games.pb" not in database_files:
            self.past_games = GameList()
            self.logger.info("Created empty past games files")
        else:
            self.past_games = GameList().parse(open(f"/home/morten/Develop/packing-report/xT-impact/automation/database/past_games.pb", "rb").read())
    
    def add_game(self, schedule_line, next_or_past):
        schedule = self.next_games if next_or_past == "n" else self.past_games
        if pd.DataFrame(schedule.games).empty or schedule_line.game_id not in pd.DataFrame(schedule.games).game_id.values:
            game = Game()
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