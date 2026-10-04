from collections.abc import Iterable

import pandas as pd


def is_own_goal(qualifiers: Iterable[list[dict] | None]) -> list[bool]:
    return [
        any(qualifier.get("type", {}).get("displayName") == "OwnGoal" for qualifier in events)
        if isinstance(events, list)
        else False
        for events in qualifiers
    ]


def get_opposition_team(team_ids: pd.Series, df_teams: pd.DataFrame) -> pd.Series:
    if "team_id" not in df_teams.columns:
        raise ValueError("df_teams is missing required column 'team_id'")
    unique_team_ids = df_teams["team_id"].unique()
    if len(unique_team_ids) != 2:
        raise ValueError(f"expected exactly 2 teams, got {len(unique_team_ids)}")
    team_id_one, team_id_two = unique_team_ids
    return team_ids.replace({team_id_one: team_id_two, team_id_two: team_id_one})


def goal_mask(events_df: pd.DataFrame) -> pd.Series:
    """Boolean mask of goal events.

    WhoScored only populates ``is_goal`` for actual goals, so every other row arrives as
    ``NaN`` in an object-dtype column. Masking with that column directly raises
    ``ValueError: Cannot mask with non-boolean array containing NA / NaN values``.
    """
    return events_df["is_goal"].eq(True)


def get_score(events_df: pd.DataFrame, df_teams: pd.DataFrame) -> pd.DataFrame:
    required_columns = ("is_goal", "qualifiers", "team_id", "expanded_minute")
    missing_columns = [column for column in required_columns if column not in events_df.columns]
    if missing_columns:
        raise KeyError(f"events_df is missing required columns: {missing_columns}")
    goals = events_df.loc[goal_mask(events_df)].copy()
    goals["own_goal"] = is_own_goal(goals["qualifiers"])
    own_goal_mask = goals["own_goal"]
    goals.loc[~own_goal_mask, "goal_team_id"] = goals.loc[~own_goal_mask, "team_id"]
    goals.loc[own_goal_mask, "goal_team_id"] = get_opposition_team(goals.loc[own_goal_mask, "team_id"], df_teams)
    return goals[["expanded_minute", "goal_team_id"]].reset_index(drop=True)
