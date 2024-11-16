
import numpy as np
import arviz as az

class MOV_Regressor:
    def __init__(self, path):
        self.trace = az.from_netcdf(path)

    def predict(self, home, elo_diff, minutes, elo_diff_faktor, goal_diff_faktor, minutes_faktor):
        # preprocess data
        elo_diff = elo_diff / elo_diff_faktor
        minutes = minutes / minutes_faktor

        pred = ((self.trace.posterior.home_advantage[0].values * home) + 
               (self.trace.posterior.power_three[0].values * elo_diff) -
               (self.trace.posterior.minutes_inf[0].values * minutes))
        
        return np.sort(np.rint(np.percentile(pred, [20, 80]) * goal_diff_faktor))