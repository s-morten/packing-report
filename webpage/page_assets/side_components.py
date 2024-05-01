import dash_mantine_components as dmc
import dash
from dash import html
from dash.dependencies import Input, Output, State
from dash import dcc
import dash_bootstrap_components as dbc
from page_assets.styling import colors


def footer():
    return dmc.Footer(
            height=50,
            fixed=True,
            children=[dmc.Text("Company Logo")],
            style={"backgroundColor": colors["dark"]},
        )

def header(app):
    return dmc.Header(
                height=50, children=[
                    offcanvas_layout(app)
                ],
                style={"backgroundColor": colors["dark"]}
            )


def offcanvas_layout(app):
    return  html.Div([
                html.Div([
                    dbc.Button("Menu", id="open-offcanvas", n_clicks=0, style={"backgroundColor": colors["middle"]}),
                    dbc.Offcanvas([
                        html.Div(
                            dcc.Link(
                                f"GDE", href="/gde"
                        )),
                        html.Div(
                            dcc.Link(
                                f"GDE Trend", href="/gde_trend"
                        )),
                        html.Div(
                            dcc.Link(
                                f"GDE Team", href="/gde_team"
                        )),
                        # Button to open the "Buy Me a Coffee" widget in a new window
                        html.A([
                            html.Img(
                                src=app.get_asset_url('coffee.jpg'),
                                style={
                                    'height' : '80px',
                                    'width' : '80px',
                                    'float' : 'left',
                                    'position' : 'relative',
                                    'padding-top' : 0,
                                    'padding-right' : 0
                                })
                                # TODO real buymeacoffe
                        ], href="https://www.buymeacoffee.com/mortenstehR"),
                        html.Img(
                                src=app.get_asset_url('simple_logo.jpg'),
                                style={
                                    'height' : '80px',
                                    'width' : '80px',
                                    'float' : 'left',
                                    'position' : 'relative',
                                    'padding-top' : 0,
                                    'padding-right' : 0
                                })
                    ],
                        id="offcanvas",
                        title="MoSt Analytics",
                        is_open=False,
                    )
                ])
            ])

def register_callbacks(app):
    @app.callback(
        Output("offcanvas", "is_open"),
        Input("open-offcanvas", "n_clicks"),
        [State("offcanvas", "is_open")],
    )
    def toggle_offcanvas(n1, is_open):
        if n1:
            return not is_open
        return is_open