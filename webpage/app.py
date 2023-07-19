# file app.py
import dash
from dash import dcc
from dash import html
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import Input, Output, State, html

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.SLATE], use_pages=True)
app.layout = html.Div([
    html.Div([
        dbc.Button("Open Offcanvas", id="open-offcanvas", n_clicks=0),
        dbc.Offcanvas([
            html.Div(
                dcc.Link(
                    f"Tables", href="/tables"
            )),
            html.Div(
                dcc.Link(
                    f"Test", href="/test"
            ))
        ],
            id="offcanvas",
            title="Title",
            is_open=False,
        ),
        dash.page_container
    ])
])

@app.callback(
    Output("offcanvas", "is_open"),
    Input("open-offcanvas", "n_clicks"),
    [State("offcanvas", "is_open")],
)
def toggle_offcanvas(n1, is_open):
    if n1:
        return not is_open
    return is_open


if __name__ == '__main__':
    app.run_server(debug=True)