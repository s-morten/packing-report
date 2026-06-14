from database_io.models.legacy import Prediction


class DB_predictions:
    def insert_prediction(
        self,
        session,
        id: int,
        home_elo: float,
        away_elo: float,
        prediction_low: float,
        prediction_high: float,
        result: str,
    ):
        pred = Prediction(
            game_id=int(id),
            home_elo=float(home_elo),
            away_elo=float(away_elo),
            prediction_low=float(prediction_low),
            prediction_high=float(prediction_high),
            result=str(result),
        )
        session.add(pred)
        session.commit()
