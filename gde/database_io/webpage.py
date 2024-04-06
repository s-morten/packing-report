from gde.database_io.db_handler_abs import DB_handler_abs
from gde.database_io.faks import Player
from gde.database_io.dims import Elo, Games
from sqlalchemy import func


class DB_webpage(DB_handler_abs):
    def get_table_data(self, entries_per_page, prev_page_clicks, next_page_clicks, league_select):
        # Subquery to get the latest game_date for each player
        dist_elo = (
            self.session.query(
                Elo.player_id,
                func.max(Elo.game_date).label("game_date")
            )
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
                Player.id,
                Player.name,
                Player.birthday, 
                Games.league, 
                Games.team_id
            )
            .join(Player, joined_elo.c.player_id == Player.id)
            .join(Games, (Games.game_id == joined_elo.c.game_id) & (Games.player_id == joined_elo.c.player_id))
            .filter(Games.league.in_(league_select))
            .order_by(joined_elo.c.elo_value.desc())
            .limit(entries_per_page)
            .offset(max(0, (prev_page_clicks - 2) * entries_per_page) if prev_page_clicks > 0
                    else (next_page_clicks - 1) * entries_per_page if next_page_clicks > 0
                    else 0)
        ).all()
        return result