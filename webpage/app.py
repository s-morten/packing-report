# file app.py
import dash
from dash import dcc
from dash import html
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import Input, Output, State, html
import webbrowser


colors = {
    "background": "#faf9f9",
    "dark": "#555b6e",
    "middle": "#89b0ae",
    "light": "#bee3db",
    "off": "#ffd6ba"
}

html_script = '<script data-name="BMC-Widget" data-cfasync="false" src="https://cdnjs.buymeacoffee.com/1.0.0/widget.prod.min.js" data-id="mortenstehR" data-description="Support me on Buy me a coffee!" data-message="" data-color="#40DCA5" data-position="Right" data-x_margin="18" data-y_margin="18"></script>'
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.LUX], use_pages=True)
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
            )),
            html.Div(
                dcc.Link(
                    f"GDE", href="/gde"
            )),
            # Button to open the "Buy Me a Coffee" widget in a new window
            html.A([
                html.Img(
                    src=app.get_asset_url('Ma.png'),
                    style={
                        'height' : '20%',
                        'width' : '20%',
                        'float' : 'left',
                        'position' : 'relative',
                        'padding-top' : 0,
                        'padding-right' : 0
                    })
            ], href="https://www.buymeacoffee.com/mortenstehR")
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