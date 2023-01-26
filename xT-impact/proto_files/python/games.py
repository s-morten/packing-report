# Generated by the protocol buffer compiler.  DO NOT EDIT!
# sources: games.proto
# plugin: python-betterproto
from dataclasses import dataclass
from typing import List

import betterproto


@dataclass
class Game(betterproto.Message):
    game_id: float = betterproto.float_field(1)
    game_date: str = betterproto.string_field(2)
    home_team: str = betterproto.string_field(3)
    away_team: str = betterproto.string_field(4)
    league: str = betterproto.string_field(5)


@dataclass
class GameList(betterproto.Message):
    games: List["Game"] = betterproto.message_field(1)
