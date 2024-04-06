import dash
from dash import html, dcc, Output, Input, State, callback
import plotly.graph_objects as go
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
# from app import colors, app
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, MetaData, Float, DateTime, func, and_, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import dash_bootstrap_components as dbc
import plotly.express as px
from page_assets.styling import colors

engine = create_engine('sqlite:////home/morten/Develop/packing-report/Goal-Difference-Elo-GDE/GDE.db', echo=True)
session = Session(engine)

def layout(app):
    return html.Div(children=[
        dbc.Row(                                        # Select Columns
            [
                dbc.Col(dbc.Input(id="player_id_input", placeholder="Player ID", type="text", value='74639')),
                dbc.Col(html.Div("One of three columns")),
                dbc.Col(html.Div("One of three columns")),
            ]
        ),
        dbc.Row(dbc.Col(dcc.Graph(id='elo_trend')))
    ])

def create_query(player_id):
    elo_game_subquery = (
    session.query(
        Elo,
        Games.minutes,
        Games.starter,
        Games.opposition_team_id,
        Games.result,
        Games.elo.label('game_elo'),
        Games.opposition_elo,
        Games.team_id,
        Games.expected_game_result,
        Games.roundend_expected_game_result
    )
    .filter(Elo.player_id == player_id)
    .join(Games, (Elo.game_id == Games.game_id) & (Elo.player_id == Games.player_id))
    .subquery()
    )

    # Main query to join elo_game_subquery and Player table
    result = (
        session.query(
            elo_game_subquery,
            Player.name
        )
        .join(Player, elo_game_subquery.c.player_id == Player.id)
    )

    return result

def top_100_all_time():
    subquery = session.query(func.max(Elo.elo_value).label("max_elo")).group_by(Elo.player_id).subquery()
    # Query to retrieve the 100th highest elo_value from the max elo values
    hundredth_highest_elo = session.query(subquery.c.max_elo).order_by(desc(subquery.c.max_elo)).limit(1).offset(99).scalar()
    return hundredth_highest_elo

def register_callbacks(app):
    @app.callback(
        Output('elo_trend', 'figure'),
        [
            Input('player_id_input', 'value'),
        ]
    )
    def update_table(player_id):
        result = create_query(int(player_id))
        elo_trend = pd.read_sql(result.statement, engine)
        fig = px.scatter(elo_trend, x="game_date", y="elo_value", hover_data=["minutes", "starter", "opposition_team_id", 
                                                                              "result", "game_elo", "opposition_elo", "game_date", 
                                                                              "team_id", "expected_game_result", "roundend_expected_game_result"
                                                                            ], color_discrete_sequence=[colors["middle"]])
        fig.add_hline(y=top_100_all_time(), line_width=2, line_dash="dash", line_color=colors["dark"])
        fig.update_layout(
            plot_bgcolor=colors["background"],  # Set the background color
            xaxis=dict(gridcolor=colors["dark"], tickfont=dict(color=colors["dark"])),
            yaxis=dict(gridcolor=colors["dark"], tickfont=dict(color=colors["dark"])),
            xaxis_title='Date',
            yaxis_title='GDE',
            title_text=elo_trend.name.unique()[0]
        )
        fig.update_xaxes(
            #tickangle=45,
            #title_font=dict(size=18, color='red')
            title_font=dict(color=colors["dark"]),
            showgrid=False
        )

        # Update y-axis properties
        fig.update_yaxes(
            title_font=dict(color=colors["dark"])
        )
        # TODO image not showing
        fig.update_layout(
            images=[dict(
                source="/home/morten/Develop/packing-report/webpage/assets/simple_logo.jpg",
                x=-0.1,
                y=0,
                xref="paper",
                yref="paper",
                sizex=0.2,
                sizey=0.2,
                opacity=1,
                layer="below"
            )]
        )
        return fig
