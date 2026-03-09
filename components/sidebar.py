from dash import html, dcc, callback, Input, Output
from config import COLORS, PAGE_ORDER, APP_NAME


def create_sidebar():
    nav_items = []
    for page in PAGE_ORDER:
        nav_items.append(
            dcc.Link(
                html.Div([
                    html.I(className=f"bi {page['icon']} me-3"),
                    html.Span(page["name"]),
                ], className="sidebar-link", id=f"nav-{page['path'].strip('/')}"),
                href=page["path"],
                className="text-decoration-none",
            )
        )

    return html.Div([
        html.Div([
            html.H4([
                html.I(className="bi bi-rocket-takeoff me-2",
                       style={"color": COLORS["primary"]}),
                APP_NAME,
            ], className="mb-0", style={"fontSize": "1.1rem", "fontWeight": "700"}),
        ], className="sidebar-header"),
        html.Hr(style={"borderColor": COLORS["card_border"], "margin": "0"}),
        html.Div(nav_items, className="sidebar-nav"),
        html.Div([
            html.Small("Keith Enterprises", style={"color": COLORS["text_muted"]}),
            html.Br(),
            html.Small("v1.0.0", style={"color": COLORS["card_border"]}),
        ], className="sidebar-footer"),
    ], className="sidebar")


@callback(
    [Output(f"nav-{page['path'].strip('/')}", "className") for page in PAGE_ORDER],
    Input("url", "pathname"),
)
def update_active_nav(pathname):
    classes = []
    for page in PAGE_ORDER:
        if pathname == page["path"] or (pathname == "/" and page["path"] == "/"):
            classes.append("sidebar-link active")
        else:
            classes.append("sidebar-link")
    return classes
