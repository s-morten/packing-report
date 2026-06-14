import numpy as np

from database_io.repositories.metric_repo import DB_metric


class Minutes:
    def __init__(self, metric_repo=None):
        self.metric_repo = metric_repo or DB_metric()

    def calculate(self, game_facts):
        loader_players_df = game_facts.loader_players_df[game_facts.loader_players_df["is_starter"]]
        players = np.swapaxes(
            [
                loader_players_df["player_id"].values,
                loader_players_df["team_id"].values,
                [0 for _ in range(len(loader_players_df["player_id"].values))],
                [-1 for _ in range(len(loader_players_df["player_id"].values))],
            ],
            0,
            1,
        )
        sub_dataframe = game_facts.events.loc[
            (game_facts.events["type"] == "SubstitutionOn") | (game_facts.events["type"] == "SubstitutionOff")
        ]
        on_dataframe = sub_dataframe.loc[(sub_dataframe["type"] == "SubstitutionOn")].copy()
        off_dataframe = sub_dataframe.loc[(sub_dataframe["type"] == "SubstitutionOff")].copy()

        subbed_on_players = np.swapaxes(
            [
                on_dataframe["player_id"].values.astype(int),
                on_dataframe["team_id"].values,
                on_dataframe["expanded_minute"].values,
                [-1 for _ in range(len(on_dataframe["player_id"].values))],
            ],
            0,
            1,
        )
        subbed_off_players = np.swapaxes(
            [
                off_dataframe["player_id"].values.astype(int),
                off_dataframe["team_id"].values,
                [0 for _ in range(len(off_dataframe["player_id"].values))],
                off_dataframe["expanded_minute"].values,
            ],
            0,
            1,
        )
        players_dict = {}
        for player in [*players, *subbed_on_players, *subbed_off_players]:
            if player[0] == 0:
                continue
            if player[0] not in players_dict:
                players_dict[player[0]] = {"team_id": player[1], "on": player[2], "off": player[3]}
            else:
                players_dict[player[0]]["on"] = max(player[2], players_dict[player[0]]["on"])
                players_dict[player[0]]["off"] = max(player[3], players_dict[player[0]]["off"])

        red_card_df = game_facts.events[
            (game_facts.events["type"] == "Card") & (game_facts.events["card_type"].isin(["SecondYellow", "Red"]))
        ]
        game_end_df = game_facts.events.loc[(game_facts.events["type"] == "End")]
        end_of_game = game_end_df[(game_end_df["period"] == "SecondHalf")]["expanded_minute"].values[0]
        if not red_card_df.empty:
            red_card_game_end = min(red_card_df["expanded_minute"].values)
            end_of_game = min(end_of_game, red_card_game_end)
        game_facts.end_of_game = end_of_game

        player_dict_keys = list(players_dict.keys())
        for player in player_dict_keys:
            if players_dict[player]["on"] > end_of_game:
                del players_dict[player]
                continue
            if (players_dict[player]["off"] == -1) or (players_dict[player]["off"] > end_of_game):
                players_dict[player]["off"] = end_of_game

        game_facts.players_dict = players_dict
        self.players_dict = players_dict

    def write(self, session, game_id):
        metric_batch = [
            [player, game_id, self.players_dict[player]["off"] - self.players_dict[player]["on"], "minutes"]
            for player in self.players_dict
        ]
        self.metric_repo.insert_batch_metric(session, metric_batch)
