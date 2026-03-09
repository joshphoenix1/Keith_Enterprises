import plotly.graph_objects as go
from config import COLORS


def dark_chart_layout(title="", height=350, showlegend=True):
    return dict(
        title=dict(text=title, font=dict(color=COLORS["text"], size=14)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS["text_muted"], size=12),
        height=height,
        margin=dict(l=50, r=30, t=50, b=40),
        showlegend=showlegend,
        legend=dict(font=dict(color=COLORS["text_muted"])),
        xaxis=dict(gridcolor=COLORS["card_border"], zerolinecolor=COLORS["card_border"]),
        yaxis=dict(gridcolor=COLORS["card_border"], zerolinecolor=COLORS["card_border"]),
    )


def gauge_chart(value, title="Score", max_val=100, height=250):
    if value >= 75:
        bar_color = COLORS["success"]
    elif value >= 50:
        bar_color = COLORS["warning"]
    else:
        bar_color = COLORS["danger"]

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title, "font": {"color": COLORS["text"], "size": 14}},
        number={"font": {"color": COLORS["text"], "size": 36}},
        gauge={
            "axis": {"range": [0, max_val], "tickcolor": COLORS["text_muted"],
                     "tickfont": {"color": COLORS["text_muted"]}},
            "bar": {"color": bar_color},
            "bgcolor": COLORS["card_border"],
            "borderwidth": 0,
            "steps": [
                {"range": [0, max_val * 0.33], "color": f"{COLORS['danger']}20"},
                {"range": [max_val * 0.33, max_val * 0.66], "color": f"{COLORS['warning']}20"},
                {"range": [max_val * 0.66, max_val], "color": f"{COLORS['success']}20"},
            ],
        },
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS["text_muted"]),
        height=height,
        margin=dict(l=30, r=30, t=50, b=20),
    )
    return fig
