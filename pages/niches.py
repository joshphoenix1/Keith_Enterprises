from dash import html, dcc
import plotly.graph_objects as go
from config import COLORS
from components.cards import info_card
from components.tables import dark_table
from components.charts import dark_chart_layout
from utils.data import load_niches


def layout():
    df = load_niches()

    # Data table
    columns = [{"name": c, "id": c} for c in df.columns]
    data = df.to_dict("records")

    # Bar chart — top 10 by revenue
    top10 = df.nlargest(10, "monthly_revenue")
    bar_fig = go.Figure(go.Bar(
        x=top10["monthly_revenue"],
        y=top10["niche"],
        orientation="h",
        marker_color=COLORS["primary"],
        text=[f"${v:,.0f}" for v in top10["monthly_revenue"]],
        textposition="auto",
        textfont=dict(color=COLORS["text"], size=11),
    ))
    bar_fig.update_layout(
        **dark_chart_layout("Top 10 Niches by Monthly Revenue", height=400, showlegend=False))
    bar_fig.update_yaxes(autorange="reversed")

    # Scatter — revenue vs competition
    trend_colors = {
        "Growing": COLORS["success"],
        "Stable": COLORS["primary"],
        "Declining": COLORS["danger"],
    }
    scatter_fig = go.Figure()
    for trend in df["trend"].unique():
        subset = df[df["trend"] == trend]
        scatter_fig.add_trace(go.Scatter(
            x=subset["competition_score"],
            y=subset["monthly_revenue"],
            mode="markers+text",
            name=trend,
            text=subset["niche"],
            textposition="top center",
            textfont=dict(size=9, color=COLORS["text_muted"]),
            marker=dict(
                size=subset["avg_reviews"] / 400,
                color=trend_colors.get(trend, COLORS["text_muted"]),
                opacity=0.8,
                line=dict(width=1, color=COLORS["card_border"]),
            ),
        ))
    scatter_layout = dark_chart_layout("Revenue vs Competition (bubble = review count)", height=420)
    scatter_layout["xaxis"]["title"] = "Competition Score"
    scatter_layout["yaxis"]["title"] = "Monthly Revenue ($)"
    scatter_fig.update_layout(**scatter_layout)

    return html.Div([
        html.Div([
            html.H2("Niche Analysis"),
            html.P("Explore and compare Amazon product niches"),
        ], className="page-header"),

        html.Div([
            html.Div([
                dcc.Graph(figure=bar_fig, config={"displayModeBar": False}),
            ], className="chart-container"),
            html.Div([
                dcc.Graph(figure=scatter_fig, config={"displayModeBar": False}),
            ], className="chart-container"),
        ], className="grid-row grid-2"),

        html.Div([
            info_card("All Niches", dark_table("niches-table", columns, data), "bi-table"),
        ], style={"marginTop": "20px"}),
    ])
