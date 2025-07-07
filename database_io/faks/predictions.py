from database_io.faks import Prediction
class DB_predictions():
    def __init__(self, connection_item):
        self.connection = connection_item.connection
        self.session = connection_item.session
        self.engine = connection_item.engine
    def insert_prediction(self, id: int, home_elo: float, away_elo: float, prediction_low: float, prediction_high: float, result: str):
        pred = Prediction(game_id=int(id), 
                          home_elo=float(home_elo),
                          away_elo=float(away_elo),
                          prediction_low=float(prediction_low),
                          prediction_high=float(prediction_high),
                          result=str(result))
        self.session.add(pred)
        self.session.commit()