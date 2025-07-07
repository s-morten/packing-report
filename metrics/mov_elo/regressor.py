
import numpy as np
import arviz as az

class MOV_Regressor:
    def __init__(self, path):
        trace = az.from_netcdf(path)
        self.posterior = trace.posterior

    def predict(self, home, elo_diff, minutes_missed, elo_diff_faktor, goal_diff_faktor, minutes_faktor):
        # preprocess data
        elo_diff = elo_diff / elo_diff_faktor
        minutes_missed = minutes_missed / minutes_faktor

        pred = ((self.posterior.home_advantage[0].values * home) + 
               (self.posterior.elo_diff_coeff[0].values * elo_diff) *
               abs(1 -  minutes_missed * self.posterior.minutes_missed_coeff[0].values))
               # (self.posterior.minutes_missed_coeff[0].values * minutes_missed))
        
        return np.sort(np.rint(np.percentile(pred, [20, 80])))