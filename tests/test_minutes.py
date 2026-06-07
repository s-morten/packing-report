import pandas as pd
import pytest
from metrics.low_level.minutes import Minutes


class FakeDBHandler:
    def __init__(self):
        self.inserted_batches = []

    class MetricHandler:
        def __init__(self, parent):
            self.parent = parent

        def insert_batch_metric(self, batch):
            self.parent.inserted_batches.append(batch)

    @property
    def metric(self):
        return self.MetricHandler(self)


def make_starter_df(players):
    return pd.DataFrame(
        {
            "player_id": [p["id"] for p in players],
            "team_id": [p["team_id"] for p in players],
            "is_starter": [True for _ in players],
        }
    )


def make_events_df(events):
    return pd.DataFrame(events)


def build_full_game_events(additional_events=None, red_card_minute=None):
    base = [
        {"type": "End", "period": "SecondHalf", "expanded_minute": 90, "player_id": 0, "team_id": 0, "card_type": None},
    ]
    if red_card_minute is not None:
        base.insert(
            0,
            {
                "type": "Card",
                "period": "SecondHalf",
                "expanded_minute": red_card_minute,
                "player_id": 99,
                "team_id": 1,
                "card_type": "Red",
            },
        )
    if additional_events:
        base = additional_events + base
    return base


class FakeGameTimeline:
    def __init__(self, loader_players_df, events_df):
        self.loader_players_df = loader_players_df
        self.events = events_df
        self.end_of_game = None
        self.players_dict = None


class TestCalculate:
    def test_two_starters_full_game(self):
        starter_df = make_starter_df(
            [
                {"id": 1, "team_id": 10},
                {"id": 2, "team_id": 20},
            ]
        )
        events_df = make_events_df(build_full_game_events())
        timeline = FakeGameTimeline(starter_df, events_df)

        minutes = Minutes(FakeDBHandler())
        minutes.calculate(timeline)

        assert timeline.players_dict[1]["on"] == 0
        assert timeline.players_dict[1]["off"] == 90
        assert timeline.players_dict[2]["on"] == 0
        assert timeline.players_dict[2]["off"] == 90
        assert timeline.end_of_game == 90

    def test_substitution(self):
        starter_df = make_starter_df(
            [
                {"id": 1, "team_id": 10},
            ]
        )
        events = build_full_game_events(
            additional_events=[
                {
                    "type": "SubstitutionOff",
                    "period": "SecondHalf",
                    "expanded_minute": 60,
                    "player_id": 1,
                    "team_id": 10,
                    "card_type": None,
                },
                {
                    "type": "SubstitutionOn",
                    "period": "SecondHalf",
                    "expanded_minute": 60,
                    "player_id": 11,
                    "team_id": 10,
                    "card_type": None,
                },
            ]
        )
        events_df = make_events_df(events)
        timeline = FakeGameTimeline(starter_df, events_df)

        minutes = Minutes(FakeDBHandler())
        minutes.calculate(timeline)

        assert timeline.players_dict[1]["on"] == 0
        assert timeline.players_dict[1]["off"] == 60
        assert timeline.players_dict[11]["on"] == 60
        assert timeline.players_dict[11]["off"] == 90

    def test_multiple_subs(self):
        starter_df = make_starter_df(
            [
                {"id": 1, "team_id": 10},
                {"id": 2, "team_id": 10},
            ]
        )
        events = build_full_game_events(
            additional_events=[
                {
                    "type": "SubstitutionOff",
                    "period": "SecondHalf",
                    "expanded_minute": 45,
                    "player_id": 1,
                    "team_id": 10,
                    "card_type": None,
                },
                {
                    "type": "SubstitutionOn",
                    "period": "SecondHalf",
                    "expanded_minute": 45,
                    "player_id": 11,
                    "team_id": 10,
                    "card_type": None,
                },
                {
                    "type": "SubstitutionOff",
                    "period": "SecondHalf",
                    "expanded_minute": 70,
                    "player_id": 2,
                    "team_id": 10,
                    "card_type": None,
                },
                {
                    "type": "SubstitutionOn",
                    "period": "SecondHalf",
                    "expanded_minute": 70,
                    "player_id": 12,
                    "team_id": 10,
                    "card_type": None,
                },
            ]
        )
        events_df = make_events_df(events)
        timeline = FakeGameTimeline(starter_df, events_df)

        minutes = Minutes(FakeDBHandler())
        minutes.calculate(timeline)

        assert timeline.players_dict[1]["off"] == 45
        assert timeline.players_dict[2]["off"] == 70
        assert timeline.players_dict[11]["on"] == 45
        assert timeline.players_dict[11]["off"] == 90
        assert timeline.players_dict[12]["on"] == 70
        assert timeline.players_dict[12]["off"] == 90

    def test_player_id_zero_skipped(self):
        starter_df = make_starter_df(
            [
                {"id": 0, "team_id": 10},
                {"id": 1, "team_id": 10},
            ]
        )
        events_df = make_events_df(build_full_game_events())
        timeline = FakeGameTimeline(starter_df, events_df)

        minutes = Minutes(FakeDBHandler())
        minutes.calculate(timeline)

        assert 0 not in timeline.players_dict
        assert 1 in timeline.players_dict

    def test_red_card_ends_game_early(self):
        starter_df = make_starter_df(
            [
                {"id": 1, "team_id": 10},
                {"id": 2, "team_id": 20},
            ]
        )
        events = build_full_game_events(red_card_minute=75)
        events_df = make_events_df(events)
        timeline = FakeGameTimeline(starter_df, events_df)

        minutes = Minutes(FakeDBHandler())
        minutes.calculate(timeline)

        assert timeline.end_of_game == 75
        assert timeline.players_dict[1]["off"] == 75
        assert timeline.players_dict[2]["off"] == 75

    def test_sub_after_red_card_removed(self):
        starter_df = make_starter_df(
            [
                {"id": 1, "team_id": 10},
            ]
        )
        events = build_full_game_events(
            red_card_minute=70,
            additional_events=[
                {
                    "type": "SubstitutionOn",
                    "period": "SecondHalf",
                    "expanded_minute": 80,
                    "player_id": 11,
                    "team_id": 10,
                    "card_type": None,
                },
            ],
        )
        events_df = make_events_df(events)
        timeline = FakeGameTimeline(starter_df, events_df)

        minutes = Minutes(FakeDBHandler())
        minutes.calculate(timeline)

        assert timeline.end_of_game == 70
        assert 11 not in timeline.players_dict

    def test_off_minus_one_becomes_end_of_game(self):
        starter_df = make_starter_df(
            [
                {"id": 1, "team_id": 10},
            ]
        )
        events_df = make_events_df(build_full_game_events())
        timeline = FakeGameTimeline(starter_df, events_df)

        minutes = Minutes(FakeDBHandler())
        minutes.calculate(timeline)

        assert timeline.players_dict[1]["off"] == 90

    def test_end_of_game_stored_on_timeline(self):
        starter_df = make_starter_df(
            [
                {"id": 1, "team_id": 10},
            ]
        )
        events_df = make_events_df(build_full_game_events())
        timeline = FakeGameTimeline(starter_df, events_df)

        minutes = Minutes(FakeDBHandler())
        minutes.calculate(timeline)

        assert timeline.end_of_game == 90

    def test_no_second_half_end_raises(self):
        starter_df = make_starter_df(
            [
                {"id": 1, "team_id": 10},
            ]
        )
        events_df = make_events_df(
            [
                {
                    "type": "End",
                    "period": "FirstHalf",
                    "expanded_minute": 45,
                    "player_id": 0,
                    "team_id": 0,
                    "card_type": None,
                },
            ]
        )
        timeline = FakeGameTimeline(starter_df, events_df)

        minutes = Minutes(FakeDBHandler())
        with pytest.raises(IndexError):
            minutes.calculate(timeline)

    def test_only_second_half_end_used(self):
        starter_df = make_starter_df(
            [
                {"id": 1, "team_id": 10},
            ]
        )
        events = [
            {
                "type": "End",
                "period": "FirstHalf",
                "expanded_minute": 45,
                "player_id": 0,
                "team_id": 0,
                "card_type": None,
            },
            {
                "type": "End",
                "period": "SecondHalf",
                "expanded_minute": 90,
                "player_id": 0,
                "team_id": 0,
                "card_type": None,
            },
        ]
        events_df = make_events_df(events)
        timeline = FakeGameTimeline(starter_df, events_df)

        minutes = Minutes(FakeDBHandler())
        minutes.calculate(timeline)

        assert timeline.end_of_game == 90

    def test_starter_not_in_players_dict_if_not_in_loader(self):
        starter_df = make_starter_df(
            [
                {"id": 1, "team_id": 10},
            ]
        )
        events_df = make_events_df(
            [
                {
                    "type": "End",
                    "period": "SecondHalf",
                    "expanded_minute": 90,
                    "player_id": 0,
                    "team_id": 0,
                    "card_type": None,
                },
            ]
        )
        timeline = FakeGameTimeline(starter_df, events_df)

        minutes = Minutes(FakeDBHandler())
        minutes.calculate(timeline)

        assert timeline.players_dict[1]["on"] == 0
        assert timeline.players_dict[1]["off"] == 90


class TestWrite:
    def test_writes_minutes_to_db(self):
        dbh = FakeDBHandler()
        minutes = Minutes(dbh)
        minutes.players_dict = {
            1: {"team_id": 10, "on": 0, "off": 90},
            2: {"team_id": 10, "on": 60, "off": 85},
        }

        minutes.write(game_id=42)

        assert len(dbh.inserted_batches) == 1
        batch = dbh.inserted_batches[0]
        assert [1, 42, 90, "minutes"] in batch
        assert [2, 42, 25, "minutes"] in batch

    def test_empty_dict_writes_empty(self):
        dbh = FakeDBHandler()
        minutes = Minutes(dbh)
        minutes.players_dict = {}

        minutes.write(game_id=1)

        assert dbh.inserted_batches == [[]]

    def test_write_without_calculate_raises(self):
        minutes = Minutes(FakeDBHandler())
        with pytest.raises(AttributeError):
            minutes.write(game_id=1)
