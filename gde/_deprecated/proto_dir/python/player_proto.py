# Generated by the protocol buffer compiler.  DO NOT EDIT!
# sources: player_proto.proto
# plugin: python-betterproto
from dataclasses import dataclass
from datetime import datetime
from typing import List

import betterproto


@dataclass
class Game(betterproto.Message):
    game_id: float = betterproto.float_field(1)
    game_date: datetime = betterproto.message_field(2)
    starter: bool = betterproto.bool_field(3)
    team_id: int = betterproto.int32_field(4)
    team_name: str = betterproto.string_field(11)
    home: bool = betterproto.bool_field(5)
    minutes_played: int = betterproto.int32_field(6)
    elo: float = betterproto.float_field(7)
    k: float = betterproto.float_field(8)
    goal_difference: int = betterproto.int32_field(9)
    opp_average_elo: float = betterproto.float_field(10)


@dataclass
class PlayerProto(betterproto.Message):
    player_id: int = betterproto.int32_field(1)
    player_name: str = betterproto.string_field(2)
    born: datetime = betterproto.message_field(3)
    game: List["Game"] = betterproto.message_field(4)