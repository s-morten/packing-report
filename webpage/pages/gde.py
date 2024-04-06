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

def layout(app):
    return dbc.Container([
        dbc.Row(                                        # Select Columns
            [
                dbc.Col(),
                dbc.Col(dmc.DatePicker(
                            id="date-picker",
                            label="Point in time",
                            #description="You can also provide a description",
                            minDate=date(2020, 8, 5),
                            value=datetime.now().date(),
                            #style={"width": 200},
                        )), # league
                dbc.Col(dmc.NumberInput(
                            label="Max Player Age",
                            #description="From 0 to infinity, in steps of 5",
                            value=50,
                            min=0,
                            step=1,
                            #style={"width": 250},
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
                        #style={"width": 400, "marginBottom": 10},
                    )), # minutes
                dbc.Col(        
                    dmc.MultiSelect(
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
                        #style={"width": 400, "marginBottom": 10},
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


def register_callbacks(app, dbh):
    @app.callback(
        Output('elo_table', 'figure'),
        [
            Input('commit-button', 'n_clicks'),
            Input('entries-per-page', 'value'),
            Input('prev-page-button', 'n_clicks'),
            Input('next-page-button', 'n_clicks'),
            Input('league-select', 'value'),
        ]
    )
    def update_table(n_clicks, entries_per_page, prev_page_clicks, next_page_clicks, league_select):
        result = dbh.webpage.get_table_data(entries_per_page, prev_page_clicks, next_page_clicks, league_select)
        result_df = pd.DataFrame(result, columns=['Rank', 'Id', 'Last Updated', 'Elo', 'Id', 'Name', 'Birth Date', 'League', 'Club ID'])
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
