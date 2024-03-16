import pandas as pd
from datetime import datetime
from gde.database_io.db_handler import DB_handler
from gde.database_io.dims import Games

from sqlalchemy import func


class DB_games(DB_handler):
    def insert_game(self, game_id: int, player_id: int, minutes: int, starter: bool, 
                    opposition_team_id: int, result: str, elo: float, opposition_elo: float, 
                    game_date: datetime, team_id: int, expected_game_result: float, 
                    roundend_expected_game_result: float, league: str):
        game = Games(game_id=int(game_id), player_id=int(player_id), minutes=int(minutes), starter=int(starter), opposition_team_id=int(opposition_team_id),
                            result=str(result), elo=float(elo), opposition_elo=float(opposition_elo), game_date=game_date.strftime("%Y-%m-%d"),
                            team_id=int(team_id), expected_game_result=float(expected_game_result), 
                            roundend_expected_game_result=float(roundend_expected_game_result), league=str(league))
        self.session.add(game)
        self.session.commit()

    def get_all_games(self):
        query_result = self.session.query(Games.minutes, Games.elo, Games.opposition_elo, Games.result).all()
        df = pd.DataFrame(query_result, columns=['minutes', 'elo', 'opposition_elo', 'result'])
        return df

    def get_number_of_games(self):
        query_result = self.session.query(func.count(Games.game_id.distinct())).scalar()
        return query_result