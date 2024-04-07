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
import numpy as np
from datetime import datetime, date

def layout(app, dbh):
    return dbc.Container([
        dbc.Row(                                        # Select Columns
            [
                dbc.Col(),
                dbc.Col(dmc.DatePicker(
                            id="date-picker",
                            label="Point in time",
                            minDate=date(2016, 8, 5),
                            value=date(2022, 5, 1),
                        )), # league
                dbc.Col(dmc.NumberInput(
                            label="Max Player Age",
                            value=50,
                            min=0,
                            step=1,
                        )), # teams
                dbc.Col(        
                    dmc.MultiSelect(
                        label="League",
                        placeholder="*",
                        id="league-select",
                        value=["GER-Bundesliga"],
                        # TODO get by query
                        data=[
                            {"value": "GER-Bundesliga", "label": "Bundesliga"},
                            {"value": "GER-Bundesliga2", "label": "2. Bundesliga"},
                            {"value": "ENG-Premier League", "label": "Prem"},
                        ],
                    )), # minutes
                dbc.Col(        
                    dmc.MultiSelect(
                        label="Club",
                        id="club-multi-select"
                    )),
                dbc.Col(dbc.Button("Commit", id="commit-button", outline=True, color="dark", size="sm"), align="center")
            ],
            justify="around"
        ),
        dbc.Row(dbc.Col(dcc.Graph(id='elo_table'))), # Table
        dbc.Row(                                     # Left, right
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


def register_callbacks(app, dbh):
    @app.callback(
        Output('club-multi-select', 'data'),
        [
            Input('league-select', 'value'),
            Input('date-picker', 'value')
        ]
    )
    def get_club_select(league_select, date_select):
        clubs = dbh.webpage.get_clubs(league_select, date_select)
        return [{"value": club, "label": club} for club in clubs]

    @app.callback(
        Output('elo_table', 'figure'),
        [
            Input('commit-button', 'n_clicks'),
            Input('entries-per-page', 'value'),
            Input('prev-page-button', 'n_clicks'),
            Input('next-page-button', 'n_clicks'),
            Input('league-select', 'value'),
            Input('date-picker', 'value'),
            Input('club-multi-select', 'value')
        ]
    )
    def update_table(n_clicks, entries_per_page, prev_page_clicks, next_page_clicks, league_select, date_select, club_select):
        # print(np.array(club_select).flatten())
        club_select = club_select if club_select else None
        # print(np.array(club_select).flatten())
        # print("---")
        result = dbh.webpage.get_table_data(entries_per_page, prev_page_clicks, next_page_clicks, league_select, date_select, np.array(club_select).flatten() if club_select is not None else None)
        result_df = pd.DataFrame(result, columns=['Rank', 'Id', 'Last Updated', 'Elo', 'Name', 'Birth Date', 'League', 'Club'])
        fig = go.Figure(data=[go.Table(
            header=dict(values=result_df.columns,
                        line_color=colors["dark"],
                        fill_color=colors["middle"],
                        align='center'),
            cells=dict(values=result_df.T.values,
                    line_color=colors["dark"],
                    fill_color=colors["background"],
                    align='center'))
        ])
        fig.update_layout(
            autosize=True
        )
        return fig
