from gde.database_io.db_handler_abs import DB_handler_abs
from gde.database_io.faks import Player, Team
from gde.database_io.dims import Elo, Games
from sqlalchemy import func
import numpy as np
from time import sleep


class DB_webpage(DB_handler_abs):
    def get_table_data(self, entries_per_page, prev_page_clicks, next_page_clicks, league_select, date_select, club_select):
        print(club_select)
        # Subquery to get the latest game_date for each player
        dist_elo = (
            self.session.query(
                Elo.player_id,
                func.max(Elo.game_date).label("game_date")
            )
            .filter(Elo.version == 0.2)
            .group_by(Elo.player_id)
            .subquery()
        )

        # Subquery to join dist_elo with elo table
        joined_elo = (
            self.session.query(
                dist_elo.c.player_id,
                Elo.game_date,
                Elo.elo_value, 
                Elo.game_id
            )
            .filter(Elo.version == 0.2)
            .join(Elo, (
                Elo.player_id == dist_elo.c.player_id
            ) & (
                dist_elo.c.game_date == Elo.game_date
            ))
            .subquery()
        )

        # Main query with ROW_NUMBER() and joining player table
        result = (
            self.session.query(
                func.row_number().over(order_by=joined_elo.c.elo_value.desc()).label("Rk"),
                joined_elo.c.player_id,
                joined_elo.c.game_date,
                joined_elo.c.elo_value,
                Player.name,
                Player.birthday, 
                Games.league, 
                Team.name
                #Games.team_id
            )
            .join(Player, joined_elo.c.player_id == Player.id)
            .join(Games, (Games.game_id == joined_elo.c.game_id) & (Games.player_id == joined_elo.c.player_id))
            .join(Team, Team.id == Games.team_id)
            .filter(Games.league.in_(league_select), Games.game_date > date_select)
            .filter(Games.version == 0.2)
            .filter(Team.name.in_(club_select) if club_select is not None else True)
            .order_by(joined_elo.c.elo_value.desc())
            .limit(entries_per_page)
            .offset(max(0, (prev_page_clicks - 2) * entries_per_page) if prev_page_clicks > 0
                    else (next_page_clicks - 1) * entries_per_page if next_page_clicks > 0
                    else 0)
        ).all()
        return result
    
    def get_clubs(self, league, date):
        # TODO very bad solution of fixing database problems with sqlalchemy multithreading 
        # https://stackoverflow.com/questions/41279157/connection-problems-with-sqlalchemy-and-multiple-processes
        sleep(1)
        result = (
            self.session.query(
                Team.name
            )
            .join(Games, Team.id == Games.team_id)
            .filter(Games.league.in_(league), Games.game_date > date)
        ).distinct().all()
        return np.array(result)
    
    def get_team_table(self, min_date, max_date, league):
        max_elo_date = (
            self.session.query(
                Elo.player_id,
                func.max(Elo.game_date).label("found_date")
            )
            .filter(Elo.game_date >= min_date)
            .filter(Elo.game_date <= max_date)
            .group_by(Elo.player_id)
            .subquery()
        )

        filterd_elo = (
            self.session.query(
                Elo.player_id,
                Elo.elo_value, 
                Elo.game_id
            )
            .join(max_elo_date, (
                Elo.player_id == max_elo_date.c.player_id
            ) & (
                max_elo_date.c.found_date == Elo.game_date
            )).subquery()
        )

        get_games = (
            self.session.query(
                Games.team_id,
                func.avg(filterd_elo.c.elo_value).label("strength")
            )
            .join(filterd_elo, 
                  (Games.player_id == filterd_elo.c.player_id) 
                  & (filterd_elo.c.game_id == Games.game_id))
            .group_by(Games.team_id)
            .subquery()
        )

        result = (
            self.session.query(
                Team.name, 
                get_games.c.strength    
            )
            .join(get_games, Team.id == get_games.c.team_id)
            .order_by(get_games.c.strength.desc())
            # .all()      
        )
        print(result)

        return result