# TODO: fix this monstrosity
import sys
sys.path.append("/home/morten/Develop/packing-report/")
print(sys.path)
# file app.py
import dash
from dash import dcc
from dash import html
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import Input, Output, State, html
import webbrowser
from pages import gde, gde_trend
import page_assets.side_components as custum_side_comp
from gde.database_io.db_handler import DB_handler

dbh = DB_handler("/home/morten/Develop/packing-report/gde/GDE.db")

#html_script = '<script data-name="BMC-Widget" data-cfasync="false" src="https://cdnjs.buymeacoffee.com/1.0.0/widget.prod.min.js" data-id="mortenstehR" data-description="Support me on Buy me a coffee!" data-message="" data-color="#40DCA5" data-position="Right" data-x_margin="18" data-y_margin="18"></script>'
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.LUX], 
                use_pages=True, suppress_callback_exceptions=True)

app.layout = html.Div([
    #html.H1("Test"),
    dcc.Location(id='url', refresh=False),
    custum_side_comp.header(app),
    html.Div(id='page-content'),
    custum_side_comp.footer()
])

@app.callback(Output('page-content', 'children'),
              [Input('url', 'pathname')])
def display_page(pathname):
    if pathname == '/gde':
        return gde.layout(app)
    elif pathname == '/gde_trend':
        return gde_trend.layout(app)
    else:
        return html.Div()

gde.register_callbacks(app, dbh)
custum_side_comp.register_callbacks(app)
gde_trend.register_callbacks(app)

if __name__ == '__main__':
    app.run_server(debug=True)