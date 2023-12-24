import numpy as np
from datetime import datetime, timezone

def to_season(date: datetime) -> str:
    """ Converts datetime date to season str. 
        Exp: 12.12.22 -> 2022/2023
    """
    year = int(date.year)
    if int(date.month) < 7:
        return f"{year-1}/{year}"
    else:
        return f"{year}/{year+1}"
    
def to_datetime(date: np.datetime64) -> datetime:
    """
    Converts a numpy datetime64 object to a python datetime object 
    Input:
      date - a np.datetime64 object
    Output:
      DATE - a python datetime object
    """
    timestamp = ((date - np.datetime64('1970-01-01T00:00:00'))
                 / np.timedelta64(1, 's'))
    return datetime.utcfromtimestamp(timestamp).replace(tzinfo=timezone.utc)
        