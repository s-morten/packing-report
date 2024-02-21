import dash
from dash import html, dcc, Output, Input, State, callback
import plotly.graph_objects as go
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
# from app import colors, app
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, MetaData, Float, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import dash_bootstrap_components as dbc
from page_assets.styling import colors
import dash_mantine_components as dmc
from datetime import datetime, date


engine = create_engine('sqlite:////home/morten/Develop/packing-report/Goal-Difference-Elo-GDE/GDE.db', echo=True)
session = Session(engine)
# Create a base class for declarative class definitions


def layout(app):
    return dbc.Container([
        dbc.Row(                                        # Select Columns
            [
                dbc.Col(),
                dbc.Col(dmc.DatePicker(
                            id="date-picker",
                            label="Start Date",
                            description="You can also provide a description",
                            minDate=date(2020, 8, 5),
                            value=datetime.now().date(),
                            style={"width": 200},
                        )), # league
                dbc.Col(dmc.NumberInput(
                            label="Your weight in kg",
                            description="From 0 to infinity, in steps of 5",
                            value=5,
                            min=0,
                            step=5,
                            style={"width": 250},
                        )), # teams
                dbc.Col(        dmc.MultiSelect(
            label="Select frameworks",
            placeholder="Select all you like!",
            id="framework-multi-select",
            value=["ng", "vue"],
            data=[
                {"value": "react", "label": "React"},
                {"value": "ng", "label": "Angular"},
                {"value": "svelte", "label": "Svelte"},
                {"value": "vue", "label": "Vue"},
            ],
            style={"width": 400, "marginBottom": 10},
        )), # minutes
                dbc.Col(        dmc.MultiSelect(
            label="Select frameworks",
            placeholder="Select all you like!",
            id="framework-multi-select",
            value=["ng", "vue"],
            data=[
                {"value": "react", "label": "React"},
                {"value": "ng", "label": "Angular"},
                {"value": "svelte", "label": "Svelte"},
                {"value": "vue", "label": "Vue"},
            ],
            style={"width": 400, "marginBottom": 10},
        )), # last update
                dbc.Col(dbc.Button("Commit", id="commit-button", outline=True, color="dark", size="sm"), align="center")
            ],
            justify="around"
        ),
        dbc.Row(dbc.Col(dcc.Graph(id='elo_table'))), # Table
        dbc.Row(                                        # Left, right
            [   
                dbc.Col(dbc.Button('<-', id='prev-page-button', outline=True, color="dark", n_clicks=0, size="sm"), width=1, align="end"),
                dbc.Col(dbc.Select(
                    id="entries-per-page",
                        options=[
                            {'label': '25', 'value': 25},
                            {'label': '50', 'value': 50}
                        ],
                    size="sm"
                    ), width=2, align="center"
                ),
                dbc.Col(dbc.Button('->', id='next-page-button', outline=True, color="dark", n_clicks=0, size="sm"), width=1, align="start")
            ],
            justify="center"
            )
        ],
        fluid=True
    )

def create_query(entries_per_page, prev_page_clicks, next_page_clicks):
    # Subquery to get the latest game_date for each player
    dist_elo = (
        session.query(
            Elo.player_id,
            func.max(Elo.game_date).label("game_date")
        )
        .group_by(Elo.player_id)
        .subquery()
    )

    # Subquery to join dist_elo with elo table
    joined_elo = (
        session.query(
            dist_elo.c.player_id,
            Elo.game_date,
            Elo.elo_value
        )
        .join(Elo, (
            Elo.player_id == dist_elo.c.player_id
        ) & (
            dist_elo.c.game_date == Elo.game_date
        ))
        .subquery()
    )

    # Main query with ROW_NUMBER() and joining player table
    result = (
        session.query(
            func.row_number().over(order_by=joined_elo.c.elo_value.desc()).label("Rk"),
            joined_elo.c.player_id,
            joined_elo.c.game_date,
            joined_elo.c.elo_value,
            Player.id,
            Player.name,
            Player.birthday
        )
        .join(Player, joined_elo.c.player_id == Player.id)
        .order_by(joined_elo.c.elo_value.desc())
        .limit(entries_per_page)
        .offset(max(0, (prev_page_clicks - 2) * entries_per_page) if prev_page_clicks > 0
                else (next_page_clicks - 1) * entries_per_page if next_page_clicks > 0
                else 0)
    )

    return result

def register_callbacks(app):
    @app.callback(
        Output('elo_table', 'figure'),
        [
            Input('commit-button', 'n_clicks'),
            Input('entries-per-page', 'value'),
            Input('prev-page-button', 'n_clicks'),
            Input('next-page-button', 'n_clicks'),
        ]
    )
    def update_table(n_clicks, entries_per_page, prev_page_clicks, next_page_clicks):
        result = create_query(entries_per_page, prev_page_clicks, next_page_clicks)
        elo_df = pd.read_sql(result.statement, engine)
        elo_df = elo_df[["Rk", "id", "name", "birthday", "game_date", "elo_value"]]
        elo_df = elo_df.rename(columns={"id": "ID", "name": "Name", "birthday": "Birthday", "game_date": "Last updated", "elo_value": "GDE"})
        fig = go.Figure(data=[go.Table(
            header=dict(values=elo_df.columns,
                        line_color=colors["dark"],
                        fill_color=colors["middle"],
                        align='center'),
            cells=dict(values=elo_df.values.T,
                    line_color=colors["dark"],
                    fill_color=colors["background"],
                    align='center'))
        ])
        fig.update_layout(
            autosize=True
        )
        return fig
