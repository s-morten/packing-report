import dash
from dash import html, dcc, Output, Input
import plotly.graph_objects as go
import pandas as pd
import sqlite3

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
            select * from joined_elo
            join player
            on joined_elo.player_id = player.id
            order by elo_value desc"""

# Create your connection.
cnx = sqlite3.connect('/home/morten/Develop/packing-report/Goal-Difference-Elo-GDE/GDE.db')
elo_df = pd.read_sql(sql, cnx)
elo_df_50 = elo_df.iloc[:50]
cnx.close()

def draw_table(elo_df: pd.DataFrame):
    # Create table trace
    table_trace = go.Table(
        header=dict(
            values=['<b>{}</b>'.format(col) for col in elo_df.columns],
            fill_color='grey',
            font=dict(color='white'),
            align='center'
        ),
        cells=dict(
            values=elo_df.values.T,
            fill=dict(color='lightgreen'),
            align=['left', 'center', 'center', 'center', 'center', 'center'],
            font=dict(color='black', size=12)
        )
    )

    # Create figure layout
    layout = go.Layout(
        title=dict(text='GDE'),
        width=1200,
        height=700,
        xaxis=dict(
            showline=False,
            showgrid=False,
            zeroline=False,
            fixedrange=True,
            range=[0, len(elo_df.columns)+1]
        ),
        yaxis=dict(
            showline=False,
            showgrid=False,
            zeroline=False,
            fixedrange=True,
            range=[0, 50]
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    # Add annotations for column names
    # annotations = []
    # for index, col in enumerate(columns):
    #     annotations.append(dict(
    #         x=positions[index],
    #         y=nrows+0.5,
    #         text='<b>{}</b>'.format(column_names[index]),
    #         showarrow=False,
    #         xref='x',
    #         yref='y',
    #         font=dict(color='black', size=14)
    #     ))

    # # Add annotations for table cells
    # for i in range(nrows):
    #     for j, col in enumerate(columns):
    #         annotations.append(dict(
    #             x=positions[j],
    #             y=i+0.5,
    #             text=df_example_1[col].iloc[i],
    #             showarrow=False,
    #             xref='x',
    #             yref='y',
    #             font=dict(color='black', size=12)
    #         ))

    # Add annotations to the layout
    # layout.update(annotations=annotations)

    # Create and display figure
    fig = go.Figure(data=[table_trace], layout=layout)
    return fig

layout = html.Div(children=[
    dcc.Graph(figure=draw_table(elo_df_50)),
])