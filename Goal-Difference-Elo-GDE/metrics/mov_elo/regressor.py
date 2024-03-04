
from sklearn.linear_model import LinearRegression
import json
from database_io import DB_player
import numpy as np

class MOV_Regressor:
    def __init__(self, version):
        self.version = version + 1

    def update_regressor(self):
        # get data
        db = DB_player("GDE.db")
        df = db.get_all_games()
        df["elo_diff"] = df["elo"] - df["opposition_elo"]
        df["diff"] = df["result"].apply(lambda x: int(x.split("-")[0]) - int(x.split("-")[1]))
        df["minutes"] = np.where(df["elo_diff"] < 0, df["minutes"] * -1, df["minutes"])

        # train model
        lr = LinearRegression()
        lr.fit(np.array([df["elo_diff"].values, df["minutes"].values]).T, df["diff"].values.reshape(-1, 1))

        # save coef and intercept
        reg_parameters = {
            "intercept": lr.intercept_[0],
            "coefficient_elo_diff": lr.coef_[0][0],
            "coefficient_min": lr.coef_[0][1], 
            "version": self.version
                        }
        
        json.dump(reg_parameters, open("metrics/mov_elo/regressor.json", "w"))

        # log changes
        print("Updated regressor parameters: ", reg_parameters)