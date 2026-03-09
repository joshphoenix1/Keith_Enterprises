from dash import html
from config import COLORS


def kpi_card(title, value, icon, color=None, subtitle=None):
    color = color or COLORS["primary"]
    children = [
        html.Div([
            html.Div([
                html.I(className=f"bi {icon}",
                       style={"fontSize": "1.5rem", "color": color}),
            ], style={
                "width": "48px", "height": "48px", "borderRadius": "12px",
                "background": f"{color}15", "display": "flex",
                "alignItems": "center", "justifyContent": "center",
            }),
            html.Div([
                html.P(title, className="mb-0",
                       style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
                html.H3(value, className="mb-0",
                         style={"fontWeight": "700", "color": COLORS["text"]}),
                html.Small(subtitle, style={"color": COLORS["text_muted"]})
                if subtitle else None,
            ]),
        ], style={"display": "flex", "gap": "16px", "alignItems": "center"}),
    ]
    return html.Div(children, className="dash-card")


def info_card(title, children, icon=None):
    header = html.Div([
        html.I(className=f"bi {icon} me-2",
               style={"color": COLORS["primary"]}) if icon else None,
        html.H6(title, className="mb-0",
                style={"color": COLORS["text"], "fontWeight": "600"}),
    ], style={"display": "flex", "alignItems": "center", "marginBottom": "16px"})
    return html.Div([header, children], className="dash-card")


def stat_card(label, value, change=None, change_type="neutral"):
    color_map = {"up": COLORS["success"], "down": COLORS["danger"],
                 "neutral": COLORS["text_muted"]}
    icon_map = {"up": "bi-arrow-up", "down": "bi-arrow-down", "neutral": ""}
    return html.Div([
        html.P(label, style={"color": COLORS["text_muted"], "fontSize": "0.8rem",
                             "marginBottom": "4px"}),
        html.H4(value, style={"fontWeight": "700", "marginBottom": "4px",
                              "color": COLORS["text"]}),
        html.Small([
            html.I(className=f"bi {icon_map[change_type]} me-1") if change_type != "neutral" else None,
            change,
        ], style={"color": color_map[change_type]}) if change else None,
    ], className="dash-card", style={"textAlign": "center"})
