# Generated by the protocol buffer compiler.  DO NOT EDIT!
# sources: player.proto
# plugin: python-betterproto
from dataclasses import dataclass
from typing import List

import betterproto


@dataclass
class Game(betterproto.Message):
    game_id: float = betterproto.float_field(1)
    game_date: str = betterproto.string_field(2)
    x_g: float = betterproto.float_field(3)
    x_g_pm: float = betterproto.float_field(4)
    x_t: float = betterproto.float_field(5)
    x_t_pm: float = betterproto.float_field(6)
    x_d: float = betterproto.float_field(7)
    x_d_pm: float = betterproto.float_field(8)
    x_k: float = betterproto.float_field(9)
    x_k_pm: float = betterproto.float_field(10)
    g_i: float = betterproto.float_field(11)
    g_i_pm: float = betterproto.float_field(12)
    minutes_played: int = betterproto.int32_field(13)
    starter: bool = betterproto.bool_field(14)
    team: int = betterproto.int32_field(15)
    opposition_elo: float = betterproto.float_field(16)
    league_elo: float = betterproto.float_field(17)


@dataclass
class Form(betterproto.Message):
    game_date: str = betterproto.string_field(1)
    x_g_form: float = betterproto.float_field(2)
    x_t_form: float = betterproto.float_field(3)
    x_d_form: float = betterproto.float_field(4)
    x_k_form: float = betterproto.float_field(5)
    g_i_form: float = betterproto.float_field(6)


@dataclass
class XI(betterproto.Message):
    x_i: List["Game"] = betterproto.message_field(1)
    x_i_form: List["Form"] = betterproto.message_field(2)


@dataclass
class Player(betterproto.Message):
    player_id: int = betterproto.int32_field(1)
    player_name: str = betterproto.string_field(2)
    starter: "XI" = betterproto.message_field(3)
    sub: "XI" = betterproto.message_field(4)
