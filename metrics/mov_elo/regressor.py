
from sklearn.linear_model import LinearRegression
import json
from database_io.db_handler import DB_handler
import numpy as np

class MOV_Regressor:
    def __init__(self, version, elo_version):
        self.version = version + 1
        self.elo_version = elo_version

    def update_regressor(self, dbh: DB_handler):
        # get data
        df = dbh.games.get_all_games(self.elo_version)
        df["elo_diff"] = df["elo"] - df["opposition_elo"]
        df["diff"] = df["result"].apply(lambda x: int(x.split("-")[0]) - int(x.split("-")[1]))
        df["minutes"] = np.where(df["elo_diff"] < 0, df["minutes"] * -1, df["minutes"])

        # train model
        lr = LinearRegression()
        lr.fit(np.array([df["elo_diff"].values, df["elo_diff"].values**2, df["elo_diff"].values**3, 
                         df["minutes"].values]).T, df["diff"].values.reshape(-1, 1))

        # save coef and intercept
        reg_parameters = {
            "intercept": lr.intercept_[0],
            "coefficient_elo_diff1": lr.coef_[0][0],
            "coefficient_elo_diff2": lr.coef_[0][1],
            "coefficient_elo_diff3": lr.coef_[0][2],
            "coefficient_min": lr.coef_[0][3], 
            "version": self.version
                        }
        
        json.dump(reg_parameters, open("metrics/mov_elo/regressor.json", "w"))

        # log changes
        print("Updated regressor parameters: ", reg_parameters)