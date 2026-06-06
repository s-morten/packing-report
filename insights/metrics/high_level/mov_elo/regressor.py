import pickle
from pathlib import Path


class MOV_Regressor:
    def __init__(self):
        model_path = Path(__file__).resolve().parent / "ngb.pckl"
        with open(model_path, "rb") as f:
            self.ngb = pickle.load(f)

    def predict(self, home, elo_diff, minutes_missed):
        # preprocess data

        pred = self.ngb.pred_dist([[home, elo_diff, minutes_missed]])
        # return np.sort(np.rint(np.percentile(pred, [20, 80])))
        return pred.ppf(0.25), pred.ppf(0.75)
