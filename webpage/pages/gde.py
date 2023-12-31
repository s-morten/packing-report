import dash
from dash import html, dcc, Output, Input
import plotly.graph_objects as go
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
from app import colors
from plotly.tools import mpl_to_plotly

dash.register_page(__name__)

sql = """ WITH dist_elo as (
            select player_id, max(game_date) as game_date from elo group by player_id
            ),
            joined_elo as 
            (
            select elo.player_id, elo.game_date, elo.elo_value from 
                dist_elo 
            inner join 
                elo 
            on elo.player_id = dist_elo.player_id 
                and dist_elo.game_date = elo.game_date
            )
            select ROW_NUMBER () OVER ( 
                    ORDER BY elo_value desc 
                ) Rk,
                id, game_date, elo_value, name, birthday from joined_elo
            join player
            on joined_elo.player_id = player.id
            order by elo_value desc"""

# Create your connection.
cnx = sqlite3.connect('/home/morten/Develop/packing-report/Goal-Difference-Elo-GDE/GDE.db')
elo_df = pd.read_sql(sql, cnx)
elo_df_50 = elo_df.iloc[:50]
cnx.close()

def draw_table(elo_df: pd.DataFrame):
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
    return fig

layout = html.Div(children=[
    dcc.Graph(figure=draw_table(elo_df_50)),
])