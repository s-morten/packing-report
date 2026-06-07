from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import func, select

from database_io.models import Player
from database_io.models.legacy import Games
from database_io.repositories.metric_repo import metric_query
from database_io.repositories.squads_repo import squads_query


class DB_player:
    def insert_player(self, session, id: int, name: str, birthday: str):
        birthday = datetime.strptime(birthday, "%d-%m-%y") if birthday else None
        player = Player(name=str(name), id=int(id), birthday=birthday, fapi_id=None)
        session.add(player)
        session.commit()

    def player_exists(self, session, id: int) -> bool:
        return session.query(Player).filter(Player.id == id).first() is not None

    def player_has_no_bday(self, session, id: int) -> bool:
        return session.query(Player).filter(Player.id == id, Player.birthday == None).first() is not None

    def update_player_bday(self, session, id: int, birthday: str):
        birthday = datetime.strptime(birthday, "%d-%m-%y") if birthday else None
        player = session.query(Player).filter(Player.id == id).first()
        player.birthday = birthday
        session.commit()

    def update_player_fapi_id(self, session, id: int, fapi_id: int):
        player = session.query(Player).filter(Player.id == id).first()
        player.fapi_id = fapi_id
        session.commit()

    def player_by_fapi_id(self, session, fapi_id: int):
        return session.query(Player.id).filter(Player.fapi_id == fapi_id).first()

    def get_overall_info(self, session, player_ids: list[int], game_date) -> pd.DataFrame:
        games_sub = (
            select(Games.player_id, func.count().label("entries"), func.sum(Games.minutes).label("total_minutes"))
            .where(Games.game_date >= (game_date - timedelta(days=90)))
            .group_by(Games.player_id)
            .subquery()
        )
        metric_subquery = metric_query()
        squads_subquery = squads_query(game_date)
        query_results = (
            session.query(
                Player.id,
                Player.fapi_id,
                Player.birthday,
                metric_subquery.c.metric_value,
                metric_subquery.c.metric,
                squads_subquery.c.kit_number,
                squads_subquery.c.team_id,
                games_sub.c.entries,
                games_sub.c.total_minutes,
            )
            .select_from(Player)
            .outerjoin(metric_subquery, Player.id == metric_subquery.c.player_id)
            .outerjoin(squads_subquery, Player.id == squads_subquery.c.player_id)
            .outerjoin(games_sub, Player.id == games_sub.c.player_id)
            .filter(Player.id.in_(player_ids))
            .filter(metric_subquery.c.RANK == 1)
            .all()
        )

        frame = pd.DataFrame(player_ids, columns=["id"])
        results = pd.DataFrame(
            query_results,
            columns=[
                "id",
                "fapi_id",
                "birthday",
                "metric_value",
                "metric",
                "kit_number",
                "team_id",
                "entries",
                "total_minutes",
            ],
        )
        frame["exists"] = frame["id"].isin(results["id"])
        frame = frame.merge(results, on="id", how="left")
        results_pivoted = results.pivot(index="id", columns="metric", values="metric_value")
        frame = frame.merge(results_pivoted, on="id", how="left")
        frame = frame.drop(["metric_value", "metric"], axis=1)
        frame = frame.drop_duplicates()
        return frame

    def get_basic_info(self, session, player_ids: list[int], game_date) -> pd.DataFrame:
        games_sub = (
            select(Games.player_id, func.count().label("entries"), func.sum(Games.minutes).label("total_minutes"))
            .where(Games.game_date >= (game_date - timedelta(days=90)))
            .group_by(Games.player_id)
            .subquery()
        )
        squads_subquery = squads_query(game_date)
        query_results = (
            session.query(
                Player.id,
                Player.fapi_id,
                Player.birthday,
                squads_subquery.c.kit_number,
                squads_subquery.c.team_id,
                games_sub.c.entries,
                games_sub.c.total_minutes,
            )
            .select_from(Player)
            .outerjoin(squads_subquery, Player.id == squads_subquery.c.player_id)
            .outerjoin(games_sub, Player.id == games_sub.c.player_id)
            .filter(Player.id.in_(player_ids))
            .all()
        )

        frame = pd.DataFrame(player_ids, columns=["id"])
        results = pd.DataFrame(
            query_results, columns=["id", "fapi_id", "birthday", "kit_number", "team_id", "entries", "total_minutes"]
        )
        frame["exists"] = frame["id"].isin(results["id"])
        frame = frame.merge(results, on="id", how="left")
        frame = frame.drop_duplicates()
        return frame
