import pandas as pd
from datetime import datetime
from database_io.db_handler_abs import DB_handler_abs
from database_io.dims import Games

from sqlalchemy import func


class DB_games(DB_handler_abs):
    def insert_game(self, game_id: int, player_id: int, minutes: int, starter: bool, 
                    opposition_team_id: int, result: str, elo: float, opposition_elo: float, 
                    game_date: datetime, team_id: int, expected_game_result: float, 
                    roundend_expected_game_result: float, league: str, version: float, home: int):
        game = Games(game_id=int(game_id), player_id=int(player_id), minutes=int(minutes), starter=int(starter), opposition_team_id=int(opposition_team_id),
                            result=str(result), elo=float(elo), opposition_elo=float(opposition_elo), game_date=game_date.strftime("%Y-%m-%d"),
                            team_id=int(team_id), expected_game_result=float(expected_game_result), 
                            roundend_expected_game_result=float(roundend_expected_game_result), league=str(league), 
                            version=float(version), home=int(home))
        self.session.add(game)
        self.session.commit()

    def get_all_games(self, version: float):
        query_result = self.session.query(Games.minutes, Games.elo, Games.opposition_elo, Games.result).filter(Games.version == version).all()
        df = pd.DataFrame(query_result, columns=['minutes', 'elo', 'opposition_elo', 'result'])
        return df

    def get_number_of_games(self, version: float):
        query_result = self.session.query(Games.game_id.distinct()).filter(Games.version == version).count()
        return query_result
    
