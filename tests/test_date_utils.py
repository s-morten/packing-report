from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from utils.date_utils import to_datetime, to_season


class TestToSeason:
    def test_january_is_previous_season(self):
        assert to_season(datetime(2023, 1, 15)) == "2022/2023"

    def test_june_is_previous_season(self):
        assert to_season(datetime(2022, 6, 30)) == "2021/2022"

    def test_july_is_new_season(self):
        assert to_season(datetime(2022, 7, 1)) == "2022/2023"

    def test_december_is_new_season(self):
        assert to_season(datetime(2022, 12, 31)) == "2022/2023"

    def test_month_six_boundary_previous_season(self):
        assert to_season(datetime(2022, 6, 1)) == "2021/2022"

    def test_accepts_date_object(self):
        import datetime as dt

        assert to_season(dt.date(2022, 12, 31)) == "2022/2023"

    def test_accepts_timezone_aware_datetime(self):
        aware = datetime(2023, 2, 1, tzinfo=UTC)
        assert to_season(aware) == "2022/2023"


class TestToDatetime:
    def test_seconds_resolution(self):
        result = to_datetime(np.datetime64("2022-01-01T12:30:45"))

        assert result == datetime(2022, 1, 1, 12, 30, 45, tzinfo=UTC)

    def test_day_resolution_is_utc_midnight(self):
        result = to_datetime(np.datetime64("2022-01-01"))

        assert result == datetime(2022, 1, 1, tzinfo=UTC)

    def test_unix_timestamp_round_trip(self):
        epoch = datetime(2020, 6, 15, 18, 30, tzinfo=UTC)
        as_np = np.datetime64("2020-06-15T18:30:00")

        assert to_datetime(as_np) == epoch

    def test_result_is_utc_aware(self):
        result = to_datetime(np.datetime64("2022-01-01"))

        assert result.tzinfo is UTC
        assert result.utcoffset() == timedelta(0)

    def test_non_datetime64_input_raises_type_error(self):
        with pytest.raises(TypeError):
            to_datetime(datetime(2022, 1, 1))
