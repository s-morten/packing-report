import numpy as np
import pandas as pd
import pytest
from game.game_facts import GameFacts


def make_game_facts(df_teams):
    facts = object.__new__(GameFacts)
    facts.df_teams = df_teams
    facts.game_id = 123
    return facts


def make_teams_df(team_id, team_name):
    return pd.DataFrame({"team_id": [team_id], "team_name": [team_name]})


class TestResolveHomeTeamId:
    def test_matching_team_name_returns_team_id(self):
        facts = make_game_facts(make_teams_df(10, "Dortmund"))

        assert facts._resolve_home_team_id("Dortmund") == 10

    def test_returns_plain_int_when_team_id_is_numpy_type(self):
        facts = make_game_facts(make_teams_df(np.int64(10), "Dortmund"))

        result = facts._resolve_home_team_id("Dortmund")

        assert result == 10
        assert type(result) is int

    def test_matches_second_row_of_multiple_teams(self):
        df_teams = pd.DataFrame({"team_id": [20, 10], "team_name": ["Bayern", "Dortmund"]})
        facts = make_game_facts(df_teams)

        assert facts._resolve_home_team_id("Dortmund") == 10

    def test_empty_team_name_raises_value_error(self):
        facts = make_game_facts(make_teams_df(10, "Dortmund"))

        with pytest.raises(ValueError):
            facts._resolve_home_team_id("")

    def test_whitespace_team_name_raises_value_error(self):
        facts = make_game_facts(make_teams_df(10, "Dortmund"))

        with pytest.raises(ValueError):
            facts._resolve_home_team_id("   ")

    def test_empty_teams_df_raises_value_error(self):
        facts = make_game_facts(pd.DataFrame())

        with pytest.raises(ValueError):
            facts._resolve_home_team_id("Dortmund")

    def test_none_teams_df_raises_value_error(self):
        facts = make_game_facts(None)

        with pytest.raises(ValueError):
            facts._resolve_home_team_id("Dortmund")

    def test_missing_team_name_column_raises_key_error(self):
        facts = make_game_facts(pd.DataFrame({"team_id": [10]}))

        with pytest.raises(KeyError):
            facts._resolve_home_team_id("Dortmund")

    def test_missing_team_id_column_raises_key_error(self):
        facts = make_game_facts(pd.DataFrame({"team_name": ["Dortmund"]}))

        with pytest.raises(KeyError):
            facts._resolve_home_team_id("Dortmund")

    def test_unknown_team_name_raises_lookup_error(self):
        facts = make_game_facts(make_teams_df(10, "Dortmund"))

        with pytest.raises(LookupError):
            facts._resolve_home_team_id("Hamburg")

    def test_matching_is_case_insensitive(self):
        facts = make_game_facts(make_teams_df(10, "Bayern"))

        assert facts._resolve_home_team_id("bayern") == 10
