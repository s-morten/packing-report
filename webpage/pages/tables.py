import dash
from dash import html, dcc, Output, Input
import plotly.graph_objects as go
import pandas as pd

dash.register_page(__name__)

def draw_table():
    df_example_1 = pd.read_csv("/home/morten/Develop/packing-report/webpage/tables.csv", sep=",")
    ncols = 10
    nrows = df_example_1.shape[0]
    positions = [0.25, 1, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5]
    columns = ["Rk","Squad","MP","W","D","L","GF","GA","GD","Pts"]# ,"xG","xGA","xGD","Last 5"]
    column_names = ["Rk","Squad","MP","W","D","L","GF","GA","GD","Pts"]# ,"xG","xGA","xGD","Last 5"]

    # Create table trace
    table_trace = go.Table(
        header=dict(
            values=['<b>{}</b>'.format(col) for col in columns],
            fill_color='grey',
            font=dict(color='white'),
            align='center'
        ),
        cells=dict(
            values=[df_example_1[col] for col in columns],
            fill=dict(color='lightgreen'),
            align=['left', 'center', 'center', 'center', 'center'],
            font=dict(color='black', size=12)
        )
    )

    # Create figure layout
    layout = go.Layout(
        title=dict(text='Bundesliga Table'),
        width=1200,
        height=700,
        xaxis=dict(
            showline=False,
            showgrid=False,
            zeroline=False,
            fixedrange=True,
            range=[0, ncols+1]
        ),
        yaxis=dict(
            showline=False,
            showgrid=False,
            zeroline=False,
            fixedrange=True,
            range=[0, nrows]
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    # Add annotations for column names
    annotations = []
    for index, col in enumerate(columns):
        annotations.append(dict(
            x=positions[index],
            y=nrows+0.5,
            text='<b>{}</b>'.format(column_names[index]),
            showarrow=False,
            xref='x',
            yref='y',
            font=dict(color='black', size=14)
        ))

    # Add annotations for table cells
    for i in range(nrows):
        for j, col in enumerate(columns):
            annotations.append(dict(
                x=positions[j],
                y=i+0.5,
                text=df_example_1[col].iloc[i],
                showarrow=False,
                xref='x',
                yref='y',
                font=dict(color='black', size=12)
            ))

    # Add annotations to the layout
    # layout.update(annotations=annotations)

    # Create and display figure
    fig = go.Figure(data=[table_trace], layout=layout)
    return fig


layout = html.Div(children=[
    dcc.Graph(figure=draw_table()),

])
