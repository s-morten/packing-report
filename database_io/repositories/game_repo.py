from datetime import datetime

import pandas as pd

from database_io.models.legacy import Games


class DB_games:
    def insert_game(self, session, game_id: int, player_id: int, minutes: int, starter: bool,
                    opposition_team_id: int, result: str, elo: float, opposition_elo: float,
                    game_date: datetime, team_id: int, expected_game_result_lower: float,
                    expected_game_result_upper: float, league: str, version: float,
                    home: int, game_minutes: int, valid: int):
        game = Games(
            game_id=int(game_id), player_id=int(player_id), minutes=int(minutes),
            starter=int(starter), opposition_team_id=int(opposition_team_id),
            result=str(result), elo=float(elo), opposition_elo=float(opposition_elo),
            game_date=game_date, team_id=int(team_id),
            expected_game_result_lower=float(expected_game_result_lower),
            expected_game_result_upper=float(expected_game_result_upper),
            league=str(league), version=float(version), home=int(home),
            game_minutes=int(game_minutes), valid=int(valid),
        )
        session.add(game)
        session.commit()

    def get_all_games(self, session, version: float, last: int = -1):
        if last == -1:
            query_result = (
                session.query(
                    Games.game_id, Games.minutes, Games.elo, Games.opposition_elo,
                    Games.result, Games.home, Games.game_minutes,
                )
                .filter(Games.version == version, Games.valid == 1)
                .all()
            )
        else:
            query_result = (
                session.query(
                    Games.game_id, Games.minutes, Games.elo, Games.opposition_elo,
                    Games.result, Games.home, Games.game_minutes,
                )
                .order_by(Games.game_date.desc())
                .limit(last)
                .all()
            )
        return pd.DataFrame(
            query_result, columns=["id", "minutes", "elo", "opposition_elo", "result", "home", "game_minutes"]
        )

    def get_number_of_games(self, session, version: float):
        return session.query(Games.game_id.distinct()).filter(Games.version == version).count()

    def insert_games_batch(self, session, games: list[list]):
        converted_games = [
            Games(
                game_id=int(g[0]), player_id=int(g[1]), minutes=int(g[2]),
                starter=int(g[3]), opposition_team_id=int(g[4]), result=str(g[5]),
                elo=float(g[6]), opposition_elo=float(g[7]), game_date=g[8],
                team_id=int(g[9]), expected_game_result_lower=float(g[10]),
                expected_game_result_upper=float(g[11]), league=str(g[12]),
                version=float(g[13]), home=int(g[14]), game_minutes=int(g[15]),
                valid=int(g[16]),
            )
            for g in games
        ]
        session.bulk_save_objects(converted_games)
        session.commit()
