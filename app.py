import dash
from dash import html, dcc, callback, Input, Output
from config import COLORS, APP_NAME, APP_PORT
from components.sidebar import create_sidebar

app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    title=APP_NAME,
    external_stylesheets=[
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
    ],
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
    ],
)

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    create_sidebar(),
    html.Div(id="page-content", className="main-content"),
], style={"backgroundColor": COLORS["bg"], "minHeight": "100vh"})


@callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname):
    if pathname == "/" or pathname is None:
        from pages.home import layout
        return layout()
    elif pathname == "/inbox":
        from pages.inbox import layout
        return layout()
    elif pathname == "/scanner":
        from pages.scanner import layout
        return layout()
    elif pathname == "/offers":
        from pages.offers import layout
        return layout()
    elif pathname == "/buyers":
        from pages.buyers import layout
        return layout()
    elif pathname == "/accounts":
        from pages.accounts import layout
        return layout()
    elif pathname == "/health":
        from pages.health import layout
        return layout()
    else:
        return html.Div([
            html.H2("404 — Page Not Found"),
            html.P("The page you're looking for doesn't exist."),
        ], className="page-header")


# Import page modules to register their callbacks
import pages.offers
import pages.buyers
import pages.accounts
import pages.inbox
import pages.scanner
import pages.health


if __name__ == "__main__":
    import os
    from utils.healthcheck import HealthChecker
    # Only start health checker in the reloader's child process (or non-debug mode)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not True:
        checker = HealthChecker(app=app, interval=60)
        app.server.health_checker = checker
        checker.start()
    app.run(debug=True, host="0.0.0.0", port=APP_PORT,
            dev_tools_ui=False, dev_tools_props_check=False)
