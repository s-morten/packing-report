import pandas as pd

def is_own_goal(qualifiers):
    return [max([(True if x["type"]["displayName"] == "OwnGoal" else False) for x in events], default=False) for events in qualifiers]

def get_opposition_team(df_goals: pd.DataFrame, df_teams: pd.DataFrame):
    switched_teams = df_goals.copy()
    team_id_one = df_teams["team_id"].unique()[0]
    team_id_two = df_teams["team_id"].unique()[1]
    switched_teams.replace({team_id_one : team_id_two,
                            team_id_two : team_id_one}, inplace = True)
    return switched_teams

def get_score(events_df: pd.DataFrame, df_teams: pd.DataFrame):
    goals = events_df.loc[(events_df["is_goal"] == True)].copy()
    goals["own_goal"] = is_own_goal(goals["qualifiers"])
    goals.loc[~goals["own_goal"], "goal_team_id"] = goals.loc[~goals["own_goal"],"team_id"]
    goals.loc[goals["own_goal"], "goal_team_id"] = get_opposition_team(goals["team_id"], df_teams)[goals["own_goal"]]
    goals.reset_index(inplace=True)
    return goals[["expanded_minute", "goal_team_id"]]

def replace_name(club_name, name_substitutes):
    for replace in name_substitutes:
        for name in name_substitutes[replace]:
            if name == club_name:
                return replace
    raise ValueError(f"Could not find replacement for {club_name}")