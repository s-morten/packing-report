import pymc as pm
import numpy as np
import arviz as az
import pandas as pd


class Poisson_Prediction_Model:
    _xg_mean = 1.806066777196846
    _xg_against_mean = 1.8108628961990612
    _xt_mean = 1.6983602830994018
    _xt_against_mean = 1.700501963697039
    _form_for_mean = 3.2009207497533705
    _form_against_mean = 3.1964156527458076

    _features_dummy = np.zeros((6082, 8))
    _form_dummy = np.zeros((6082, 4))
    _goals_dummy = np.zeros((6082, 2))
    _elo_diff_dummy = np.zeros((6082, 1))

    _data_size = 6082

    def model(self):
        with pm.Model() as independent_poisson:
            pm_features = pm.Data("pm_features", self._features_dummy, mutable=True)
            pm_form_diff = pm.Data("pm_form_diff", self._form_dummy, mutable=True)
            pm_goals = pm.Data("pm_goals", self._goals_dummy, mutable=True)
            pm_elo_diff = pm.Data("pm_elo_diff", self._elo_diff_dummy, mutable=True)

            coefs_features = pm.HalfNormal(
                "coefs_features",
                sigma=[
                    [1, 0.001],
                    [1, 0.001],
                    [0.001, 1],
                    [0.001, 1],
                    [1, 0.001],
                    [1, 0.001],
                    [0.001, 1],
                    [0.001, 1],
                ],
                shape=(self._features_dummy.shape[1], 2),
            )

            coefs_elo_diff = pm.Normal(
                "coefs_elo_diff", mu=[0.5, -0.5], sigma=[0.2, 0.2], shape=(1, 2)
            )

            coefs_form_diff = pm.Normal(
                "coefs_form_diff", shape=(self._form_dummy.shape[1], 2)
            )
            factor = pm.Dirichlet("factor", a=np.ones(3))
            intercepts = pm.Normal("intercepts", shape=2)

            log_lam = pm.Deterministic(
                "log_lam",
                intercepts
                + 0.1 * (pm_elo_diff @ coefs_elo_diff)
                + 0.4 * (pm_form_diff @ coefs_form_diff)
                + 0.5 * (pm_features @ coefs_features),
            )

            lam = pm.math.exp(log_lam)

            obs = pm.Poisson("obs", mu=lam, observed=pm_goals)

        return independent_poisson

    def prepare_data(self, data):
        orig_size = data.shape[0]
        size_diff = self._data_size - orig_size
        column_size = data.shape[1]
        fill_data = [np.ones(column_size) for _ in range(size_diff)]
        data_fill = pd.DataFrame(data=fill_data, columns=data.columns)
        data = pd.concat([data, data_fill])

        features = np.swapaxes(
            np.array(
                [
                    data["home_xG"] - self._xg_mean,
                    data["away_xg_against"] - self._xg_against_mean,
                    data["away_xG"] - self._xg_mean,
                    data["home_xg_against"] - self._xg_against_mean,
                    data["home_xT_all"] - self._xt_mean,
                    data["away_xT_all"] - self._xt_mean,
                    data["home_xt_all_against"] - self._xt_against_mean,
                    data["away_xt_all_against"] - self._xt_against_mean,
                ]
            ),
            0,
            1,
        )
        form = np.swapaxes(
            np.array(
                [
                    (data["ha_form_home_for"] / 5) - self._form_for_mean,
                    (data["ha_form_home_against"] / 5) - self._form_against_mean,
                    (data["ha_form_away_for"] / 5) - self._form_for_mean,
                    (data["ha_form_away_against"] / 5) - self._form_against_mean,
                ]
            ),
            0,
            1,
        )
        elo = np.swapaxes(
            np.array([(data["elo_home"] / 1000) - (data["elo_away"] / 1000)]), 0, 1
        )
        return orig_size, features, form, elo

    def get_trace(self):
        trace = az.from_netcdf("/home/morten/Develop/packing-report/xT-impact/models/traces/independent_trace.nc").load()
        return trace

    def predict(self, prediction_data):
        model = self.model()
        trace = self.get_trace()
        orig_size, features, form, elo = self.prepare_data(prediction_data)
        predictions = None
        with model:
            pm.set_data(
                {"pm_elo_diff": elo, "pm_features": features, "pm_form_diff": form}
            )

            sample_res = pm.sample_posterior_predictive(trace, predictions=True)
            predictions = sample_res["predictions"]

        predictions_home = np.swapaxes(np.array(predictions.obs[0].values), 0, 1)[
            :orig_size
        ][:, :, 0]
        predictions_away = np.swapaxes(np.array(predictions.obs[0].values), 0, 1)[
            :orig_size
        ][:, :, 1]
        game_quotes = []
        for game_idx in range(len(predictions_home)):
            home_hist, bin_edges = np.histogram(
                predictions_home[game_idx], [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
            )
            away_hist, bin_edges = np.histogram(
                predictions_away[game_idx], [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
            )
            if home_hist.shape[0] < 10:
                home_hist = np.append(home_hist, np.zeros(10 - home_hist.shape[0]))
            if away_hist.shape[0] < 10:
                away_hist = np.append(away_hist, np.zeros(10 - away_hist.shape[0]))
            home_hist = home_hist / 1000
            away_hist = away_hist / 1000
            probs = home_hist.reshape(home_hist.shape[0], 1) * away_hist
            for x in range(len(probs)):
                for y in range(len(probs[x])):
                    if x == y:
                        probs[x][y] *= 1.3
                    else:
                        probs[x][y] *= 1 - 0.085
            home = np.tril(probs).sum() - np.trace(probs)
            draw = np.trace(probs)
            away = np.triu(probs).sum() - np.trace(probs)
            game_quotes.append([home, draw, away])
        return game_quotes
