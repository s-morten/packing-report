from datetime import UTC, date, datetime

import numpy as np


def to_season(date: date) -> str:
    """Converts datetime date to season str.
    Exp: 12.12.22 -> 2022/2023
    """
    if date.month < 7:
        return f"{date.year - 1}/{date.year}"
    return f"{date.year}/{date.year + 1}"


def to_datetime(date: np.datetime64) -> datetime:
    """
    Converts a numpy datetime64 object to a python datetime object
    Input:
      date - a np.datetime64 object
    Output:
      DATE - a python datetime object
    """
    try:
        timestamp = (date - np.datetime64("1970-01-01T00:00:00")) / np.timedelta64(1, "s")
    except TypeError as e:
        raise TypeError(f"expected a np.datetime64, got {type(date).__name__}") from e
    return datetime.fromtimestamp(timestamp, tz=UTC)
