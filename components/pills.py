from dash import html
from config import COLORS


def pill(text, color=None):
    color = color or COLORS["primary"]
    return html.Span(text, style={
        "backgroundColor": f"{color}20",
        "color": color,
        "padding": "4px 12px",
        "borderRadius": "20px",
        "fontSize": "0.75rem",
        "fontWeight": "600",
        "display": "inline-block",
    })


def status_pill(status):
    status_colors = {
        "Active": COLORS["success"],
        "Under Review": COLORS["warning"],
        "Inactive": COLORS["danger"],
        "Pending": COLORS["info"],
    }
    color = status_colors.get(status, COLORS["text_muted"])
    return pill(status, color)


def verdict_pill(verdict):
    verdict_colors = {
        "GO": COLORS["success"],
        "MAYBE": COLORS["warning"],
        "NO GO": COLORS["danger"],
    }
    color = verdict_colors.get(verdict, COLORS["text_muted"])
    return pill(verdict, color)
