#!/usr/bin/python
import soccerdata as sd
from datetime import datetime
from pathlib import PosixPath
import pandas as pd
from global_packing import init_logging, LEAGUE_LIST, DEBUG
from handlers_packing import ScheduleHandler
from pathlib import Path

# read shedule every monday morning
def update_schedule(league_list):
    logger = init_logging()
    all_schedules = []
    #for league in league_list:
    ws = sd.WhoScored(
        leagues=league_list,
        seasons=[22],
        no_cache=False,
        no_store=False,
        data_dir=PosixPath("/home/morten/Develop/Open-Data/soccerdata"),
        path_to_browser=Path("/usr/bin/chromium"),
        headless=False,
    )
    schedule = ws.read_schedule()

    for idx, league in enumerate(league_list):
        all_schedules.append(schedule.loc[league, :])
        all_schedules[idx]["league_name"] = [league for _ in range(all_schedules[idx].shape[0])]

    df_schedule = pd.concat(all_schedules)
    df_schedule.columns = df_schedule.columns.to_flat_index()
    # remove games from the past
    date_now = datetime.now()
    dt_string = date_now.strftime("%Y-%m-%d %H:%M:%S")
    future_games_schedule = df_schedule.loc[df_schedule["date"] > dt_string]
    schedule_handler = ScheduleHandler()
    for idx, schedule_line in future_games_schedule.iterrows():
        schedule_handler.add_game(schedule_line, "n")        
    schedule_handler.write_schedule("n")

    ######
    if DEBUG:
        past_games_schedule = df_schedule.loc[df_schedule["date"] < dt_string]
        for idx, schedule_line in past_games_schedule.iterrows():
            schedule_handler.add_game(schedule_line, "p")        
        schedule_handler.write_schedule("p")
    ######

    logger.info("Successfully updated next games list")


if __name__ == "__main__":
    update_schedule(LEAGUE_LIST)
