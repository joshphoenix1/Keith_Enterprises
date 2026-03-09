from dash import html, dcc, callback, Input, Output
import plotly.graph_objects as go
import numpy as np
from config import COLORS
from components.cards import info_card
from components.forms import styled_slider, form_group
from components.charts import dark_chart_layout, gauge_chart


RISK_CATEGORIES = [
    {"id": "competition", "name": "Competition", "icon": "bi-people",
     "description": "Market saturation and competitor strength"},
    {"id": "ip", "name": "IP / Legal", "icon": "bi-shield-lock",
     "description": "Patent, trademark, and listing risks"},
    {"id": "supply", "name": "Supply Chain", "icon": "bi-box-seam",
     "description": "Supplier reliability and logistics risks"},
    {"id": "financial", "name": "Financial", "icon": "bi-currency-dollar",
     "description": "Margin pressure and cash flow risks"},
    {"id": "market", "name": "Market Demand", "icon": "bi-graph-down",
     "description": "Demand volatility and seasonal risks"},
]


def layout():
    risk_sliders = []
    for cat in RISK_CATEGORIES:
        risk_sliders.append(
            html.Div([
                html.Div([
                    html.I(className=f"bi {cat['icon']} me-2",
                           style={"color": COLORS["primary"]}),
                    html.Strong(cat["name"], style={"color": COLORS["text"]}),
                    html.Span(f" — {cat['description']}",
                              style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
                ], style={"marginBottom": "8px"}),
                styled_slider(
                    f"risk-{cat['id']}", min_val=1, max_val=5, value=3, step=1,
                    marks={i: {"label": str(i), "style": {"color": COLORS["text_muted"]}}
                           for i in range(1, 6)},
                ),
            ], style={"marginBottom": "24px"})
        )

    return html.Div([
        html.Div([
            html.H2("Risk Analysis"),
            html.P("Assess and visualize risk factors for your product"),
        ], className="page-header"),

        html.Div([
            html.Div([
                info_card("Risk Factors", html.Div(risk_sliders), "bi-sliders"),
            ], style={"gridColumn": "span 2"}),
            html.Div([
                info_card("Overall Risk Score",
                          html.Div(id="risk-gauge-container"), "bi-speedometer2"),
            ]),
        ], className="grid-row grid-3"),

        html.Div([
            info_card("Risk Heatmap",
                      html.Div(id="risk-heatmap-container"), "bi-grid-3x3"),
        ], style={"marginTop": "20px"}),
    ])


@callback(
    Output("risk-gauge-container", "children"),
    Output("risk-heatmap-container", "children"),
    [Input(f"risk-{cat['id']}", "value") for cat in RISK_CATEGORIES],
)
def update_risks(*values):
    avg_risk = sum(values) / len(values)
    # Invert for gauge: high risk = low score
    risk_score = max(0, 100 - (avg_risk - 1) * 25)

    gauge = dcc.Graph(
        figure=gauge_chart(risk_score, "Risk Score (higher = safer)", height=230),
        config={"displayModeBar": False},
        style={"height": "230px"},
    )

    risk_label = "Low Risk" if risk_score >= 75 else "Medium Risk" if risk_score >= 50 else "High Risk"
    risk_color = COLORS["success"] if risk_score >= 75 else COLORS["warning"] if risk_score >= 50 else COLORS["danger"]

    gauge_section = html.Div([
        gauge,
        html.Div(risk_label, style={
            "textAlign": "center", "color": risk_color,
            "fontWeight": "700", "fontSize": "1.1rem", "marginTop": "8px",
        }),
    ])

    # 5x5 Heatmap — likelihood vs impact
    categories_short = [c["name"] for c in RISK_CATEGORIES]

    # Build a 5x5 matrix: rows = impact (1-5), cols = likelihood (1-5)
    # Place each risk category in the matrix based on its slider value
    z = [[0]*5 for _ in range(5)]
    annotations = []

    for i, (cat, val) in enumerate(zip(RISK_CATEGORIES, values)):
        # Map risk to likelihood/impact coordinates
        likelihood = min(val, 5) - 1  # col index 0-4
        impact = min(max(val - 1 + (i % 2), 0), 4)  # slightly vary impact for visual spread
        z[4 - impact][likelihood] += 1
        annotations.append(dict(
            x=likelihood, y=4 - impact,
            text=cat["name"][:4],
            showarrow=False,
            font=dict(color=COLORS["text"], size=10, family="monospace"),
        ))

    # Color based on inherent risk level of position
    risk_matrix = [
        [1, 2, 3, 4, 5],
        [2, 4, 6, 8, 10],
        [3, 6, 9, 12, 15],
        [4, 8, 12, 16, 20],
        [5, 10, 15, 20, 25],
    ]

    heatmap_fig = go.Figure(go.Heatmap(
        z=risk_matrix,
        x=["Very Low", "Low", "Medium", "High", "Very High"],
        y=["Very Low", "Low", "Medium", "High", "Very High"],
        colorscale=[
            [0, "#3fb95030"], [0.3, "#d2992240"], [0.6, "#d2992280"],
            [0.8, "#f8514960"], [1.0, "#f85149"],
        ],
        showscale=False,
        text=[
            ["1", "2", "3", "4", "5"],
            ["2", "4", "6", "8", "10"],
            ["3", "6", "9", "12", "15"],
            ["4", "8", "12", "16", "20"],
            ["5", "10", "15", "20", "25"],
        ],
        texttemplate="%{text}",
        textfont=dict(color=COLORS["text_muted"], size=12),
    ))

    # Add risk category markers
    for i, (cat, val) in enumerate(zip(RISK_CATEGORIES, values)):
        likelihood_idx = min(val - 1, 4)
        impact_idx = min(max(val - 1 + (i % 2), 0), 4)
        x_labels = ["Very Low", "Low", "Medium", "High", "Very High"]
        heatmap_fig.add_trace(go.Scatter(
            x=[x_labels[likelihood_idx]],
            y=[x_labels[impact_idx]],
            mode="markers+text",
            marker=dict(size=20, color=COLORS["primary"], symbol="circle",
                        line=dict(width=2, color=COLORS["text"])),
            text=[cat["name"][:3]],
            textposition="top center",
            textfont=dict(color=COLORS["text"], size=10),
            name=cat["name"],
            showlegend=True,
        ))

    heatmap_layout = dark_chart_layout("Likelihood vs Impact Matrix", height=420)
    heatmap_layout["xaxis"]["title"] = "Likelihood"
    heatmap_layout["yaxis"]["title"] = "Impact"
    heatmap_fig.update_layout(**heatmap_layout)

    heatmap = dcc.Graph(figure=heatmap_fig, config={"displayModeBar": False})

    return gauge_section, heatmap
