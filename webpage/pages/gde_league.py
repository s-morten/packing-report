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
                            id="gde_league_date_picker",
                            label="Point in time",
                            minDate=date(2016, 8, 5),
                            value=date(2022, 5, 1),
                        )), # league
                dbc.Col(        
                    dmc.MultiSelect(
                        label="League",
                        placeholder="*",
                        id="gde_league_league_select",
                        value=["GER-Bundesliga"],
                        # TODO get by query
                        data=[
                            {"value": "GER-Bundesliga", "label": "Bundesliga"},
                            {"value": "GER-Bundesliga2", "label": "2. Bundesliga"},
                            {"value": "ENG-Premier League", "label": "Prem"},
                        ],
                    )), # minutes
            ],
            justify="around"
        ),
        dbc.Row(dbc.Col(dcc.Graph(id='gde_league_team_table'))), # Table
        ],
        fluid=True
    )


def register_callbacks(app, dbh):

    @app.callback(
        Output('gde_league_team_table', 'figure'),
        [
            Input('gde_league_league_select', 'value'),
            Input('gde_league_date_picker', 'value')
        ]
    )
    def update_table(league_select, date_select):
        result = dbh.webpage.get_team_table('2022-04-01', '2022-07-01', ["GER-Bundesliga", "GER-Bundesliga2", "ENG-Premier League"])
        result_df = pd.DataFrame(result, columns=['Team', 'str'])
        print(result_df.shape)
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
