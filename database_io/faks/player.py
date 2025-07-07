#from database_io.db_handler_abs import DB_handler_abs
from datetime import datetime
from database_io.faks import Player
from database_io.dims import Metric, Games
import pandas as pd
from sqlalchemy import func, over, and_, select
from database_io.dims.elo import elo_query
from database_io.faks.squads import squads_query

# class DB_player(DB_handler_abs):
class DB_player():
    def __init__(self, connection_item):
        self.connection = connection_item.connection
        self.session = connection_item.session
        self.engine = connection_item.engine
        
    def insert_player(self, id: int, name: str, birthday: str):
        birthday = datetime.strptime(birthday, "%d-%m-%y") if birthday else None
        player = Player(name=str(name), id=int(id), birthday=birthday, fapi_id=None)
        self.session.add(player)
        self.session.commit()

    def player_exists(self, id: int) -> bool:
        query_result = self.session.query(Player).filter(Player.id == id).first()
        return not (query_result is None)
    
    def player_has_no_bday(self, id: int) -> bool:
        query_result = self.session.query(Player).filter(Player.id == id, Player.birthday == None).first()
        return not (query_result is None)
    
    def update_player_bday(self, id: int, birthday: str):
        birthday = datetime.strptime(birthday, "%d-%m-%y") if birthday else None
        player = self.session.query(Player).filter(Player.id == id).first()
        player.birthday = birthday
        self.session.commit()

    def update_player_fapi_id(self, id: int, fapi_id: int):
        player = self.session.query(Player).filter(Player.id == id).first()
        player.fapi_id = fapi_id
        self.session.commit()

    def player_by_fapi_id(self, fapi_id: int):
        return self.session.query(Player.id).filter(Player.fapi_id == fapi_id).first()


    def get_overall_info(self, player_ids: list[int], game_date) -> pd.DataFrame: # version: float, date: datetime
        games_sub = select(
                        Games.player_id,
                        func.count().label('entries')).group_by(Games.player_id).subquery()
            
        elo_subquery = elo_query()
        squads_subquery = squads_query(game_date)
        # df -> player_id, exists, fapi_id, birthday, elo
        query_results = self.session.query(
            Player.id,
            Player.fapi_id,
            Player.birthday,
            elo_subquery.c.elo_value,
            squads_subquery.c.kit_number,
            squads_subquery.c.team_id,
            games_sub.c.entries
        ).select_from(
            Player
        ).outerjoin(
            elo_subquery,
            Player.id == elo_subquery.c.player_id
        ).outerjoin(
            squads_subquery,
            Player.id == squads_subquery.c.player_id
        ).outerjoin(
            games_sub,
            Player.id == games_sub.c.player_id
        ).filter(
            Player.id.in_(player_ids)
        ).filter(
            elo_subquery.c.RANK == 1
        ).all()

        frame = pd.DataFrame(player_ids, columns=["id"])
        results = pd.DataFrame(query_results, columns=["id", "fapi_id", "birthday", "elo", "kit_number", "team_id", "entries"])
        # set a column for if the player exists
        frame["exists"] = frame["id"].isin(results["id"])
        frame = frame.merge(results, on="id", how="left")
        return frame
    

    # To use this subquery in a different query, you can do something like:
    # result = self.session.query(subquery).filter(subquery.c.RANK == 1).all()