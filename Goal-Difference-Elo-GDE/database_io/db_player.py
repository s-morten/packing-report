import pandas as pd
from datetime import datetime
from .db_handler import DB_handler
from scraper.club_elo_scraper import ClubEloScraper

class DB_player(DB_handler):
    def insert_player(self, id: int, name: str, birthday: datetime):
        query = """
                INSERT INTO PLAYER(name, id, birthday) VALUES(?,?,?)
                """
        cur = self.db_connection.cursor()
        birthday = datetime.strptime(birthday, "%d-%m-%y").strftime("%Y-%m-%d")
        cur.execute(query, [name, id, birthday])
        self.db_connection.commit()

    def insert_elo(self, id: int, game_id: int, date: datetime, elo: float):
        query = """
                INSERT INTO ELO(player_id, game_id, game_date, elo_value) VALUES(?,?,?,?)
                """
        cur = self.db_connection.cursor()
        date = date.strftime("%Y-%m-%d")
        cur.execute(query, [id, game_id, date, elo])
        self.db_connection.commit()

    def insert_game(self, game_id: int, player_id: int, minutes: int, starter: bool, 
                    opposition_team_id: int, result: str, elo: float, opposition_elo: float, 
                    game_date: datetime, team_id: int):
        query = """
                INSERT INTO GAMES(game_id, player_id, minutes, starter, opposition_team_id, 
                result, elo, opposition_elo, game_date, team_id) VALUES(?,?,?,?,?,?,?,?,?,?)
                """
        cur = self.db_connection.cursor()
        game_date = game_date.strftime("%Y-%m-%d")
        cur.execute(query, [int(game_id), int(player_id), int(minutes), int(starter),
                            int(opposition_team_id), str(result), float(elo), float(opposition_elo),
                            game_date, int(team_id)])
        self.db_connection.commit()

    def get_elo(self, id: int, date: datetime, league: str) -> float:
        """ Extracts the Elo per player from the database
            Returns default value if player does not exists
        """
        query = f"""
                    SELECT ELO_VALUE, GAME_DATE FROM ELO
                    WHERE PLAYER_ID = {id} 
                        AND GAME_DATE < '{date.date()}'
                    ORDER BY GAME_DATE DESC
                """
        elo_result = pd.read_sql(query, self.db_connection)
        if elo_result.empty:
            return ClubEloScraper().get_avg_league_elo_by_date(pd.to_datetime(date, format="%Y-%m-%d"), league)
        return elo_result["elo_value"].values[0]
        
    def player_exists(self, id: int) -> bool:
        query = f"""
                SELECT 1
                FROM player
                WHERE id = {id};
                """
        exists = pd.read_sql(query, self.db_connection)
        return (not exists.empty)