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
from database_io.db_handler import DB_handler


def layout(app, dbh):
    return html.Div(children=[
        dbc.Row(                                        # Select Columns
            [
                dbc.Col(    
                    dcc.Dropdown(
                        id="dropdown",
                        options=[],  # Initially empty, will be populated dynamically
                        value=None,
                        placeholder="Search and select an option",
                        searchable=True,  # Enables the autocomplete feature
                        clearable=True,   # Allows clearing the selection
                    )
                )    
            ]
        ),
        dbc.Row(dbc.Col(dcc.Graph(id='elo_trend')))
    ])

# def top_100_all_time():
#     subquery = session.query(func.max(Elo.elo_value).label("max_elo")).group_by(Elo.player_id).subquery()
#     # Query to retrieve the 100th highest elo_value from the max elo values
#     hundredth_highest_elo = session.query(subquery.c.max_elo).order_by(desc(subquery.c.max_elo)).limit(1).offset(99).scalar()
#     return hundredth_highest_elo

def fetch_options_from_db(dbh: DB_handler):
    options = dbh.webpage.player_id_select()
    return [{"label": option[1], "value": option[0]} for option in options]

def register_callbacks(app, dbh: DB_handler):
    @app.callback(
        Output("dropdown", "options"),
        Input("dropdown", "value"),  # Triggered when the dropdown value changes (or initially)
    )
    def update_dropdown_options(selected_value):
        # Fetch options from the database
        options = fetch_options_from_db(dbh)
        return options

    @app.callback(
        Output('elo_trend', 'figure'),
        Input('dropdown', 'value'),
        Input('dropdown', 'label')
    )
    def update_table(player_id, name):
        elo_trend = dbh.webpage.trend(player_id)
        fig = px.scatter(elo_trend, x="game_date", y="elo_value", hover_data=["minutes", "starter", "opposition_team_id", 
                                                                              "result", "game_elo", "opposition_elo", "game_date", 
                                                                              "team_id", "expected_game_result_lower", 
                                                                              "expected_game_result_upper"
                                                                            ], color_discrete_sequence=[colors["middle"]])
        # fig.add_hline(y=top_100_all_time(), line_width=2, line_dash="dash", line_color=colors["dark"])
        fig.update_layout(
            plot_bgcolor=colors["background"],  # Set the background color
            xaxis=dict(gridcolor=colors["dark"], tickfont=dict(color=colors["dark"])),
            yaxis=dict(gridcolor=colors["dark"], tickfont=dict(color=colors["dark"])),
            xaxis_title='Date',
            yaxis_title='GDE',
            title_text=name
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
