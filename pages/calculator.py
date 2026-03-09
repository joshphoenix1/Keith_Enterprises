from dash import html, dcc, callback, Input, Output
import plotly.graph_objects as go
from config import COLORS
from components.cards import info_card
from components.forms import styled_input, form_group
from components.charts import dark_chart_layout
from utils.data import estimate_fba_fee, calc_referral_fee


def layout():
    form = html.Div([
        html.Div([
            form_group("Selling Price ($)",
                       styled_input("calc-price", "24.99", value=24.99)),
            form_group("Product Cost ($)",
                       styled_input("calc-cost", "4.50", value=4.50)),
            form_group("Weight (lb)",
                       styled_input("calc-weight", "1.2", value=1.2)),
        ], className="grid-row grid-3"),
        html.Div([
            form_group("Monthly Sales",
                       styled_input("calc-sales", "500", value=500)),
            form_group("Shipping to Amazon ($)",
                       styled_input("calc-shipping", "1.00", value=1.00)),
            form_group("Ad Spend % of Price",
                       styled_input("calc-adspend", "10", value=10)),
        ], className="grid-row grid-3"),
    ])

    return html.Div([
        html.Div([
            html.H2("FBA Calculator"),
            html.P("Detailed cost breakdown and projections"),
        ], className="page-header"),

        info_card("Input Parameters", form, "bi-sliders"),

        html.Div(id="calc-output"),
    ])


@callback(
    Output("calc-output", "children"),
    Input("calc-price", "value"),
    Input("calc-cost", "value"),
    Input("calc-weight", "value"),
    Input("calc-sales", "value"),
    Input("calc-shipping", "value"),
    Input("calc-adspend", "value"),
)
def update_calculator(price, cost, weight, sales, shipping, adspend):
    price = float(price or 0)
    cost = float(cost or 0)
    weight = float(weight or 0)
    sales = int(sales or 0)
    shipping = float(shipping or 0)
    adspend_pct = float(adspend or 0) / 100

    if price <= 0:
        return html.P("Enter a valid selling price", style={"color": COLORS["text_muted"]})

    fba_fee = estimate_fba_fee(weight)
    referral_fee = calc_referral_fee(price)
    ad_cost = round(price * adspend_pct, 2)
    total_cost = cost + fba_fee + referral_fee + shipping + ad_cost
    profit = price - total_cost
    margin = (profit / price) * 100

    # Pie chart — cost breakdown
    labels = ["Product Cost", "FBA Fee", "Referral Fee", "Shipping", "Ad Spend", "Profit"]
    values = [cost, fba_fee, referral_fee, shipping, ad_cost, max(profit, 0)]
    colors_pie = [COLORS["primary"], COLORS["warning"], COLORS["info"],
                  COLORS["purple"], COLORS["danger"], COLORS["success"]]

    pie_fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.55,
        marker=dict(colors=colors_pie),
        textinfo="label+percent",
        textfont=dict(size=11, color=COLORS["text"]),
    ))
    pie_fig.update_layout(**dark_chart_layout("Cost Breakdown per Unit", height=350, showlegend=False))

    # 12-month projection
    months = list(range(1, 13))
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    # Simulate growth: 5% month-over-month sales growth
    monthly_sales_proj = [int(sales * (1.05 ** (m - 1))) for m in months]
    monthly_revenue = [price * s for s in monthly_sales_proj]
    monthly_costs = [total_cost * s for s in monthly_sales_proj]
    monthly_profit_proj = [r - c for r, c in zip(monthly_revenue, monthly_costs)]
    cumulative_profit = []
    running = 0
    for p in monthly_profit_proj:
        running += p
        cumulative_profit.append(running)

    line_fig = go.Figure()
    line_fig.add_trace(go.Scatter(
        x=month_labels, y=monthly_revenue,
        name="Revenue", line=dict(color=COLORS["primary"], width=2),
        mode="lines+markers",
    ))
    line_fig.add_trace(go.Scatter(
        x=month_labels, y=monthly_profit_proj,
        name="Profit", line=dict(color=COLORS["success"], width=2),
        mode="lines+markers",
    ))
    line_fig.add_trace(go.Scatter(
        x=month_labels, y=cumulative_profit,
        name="Cumulative Profit", line=dict(color=COLORS["warning"], width=2, dash="dash"),
        mode="lines",
    ))
    line_fig.update_layout(**dark_chart_layout("12-Month Projection (5% MoM Growth)", height=380))

    # Summary cards
    annual_profit = sum(monthly_profit_proj)
    annual_revenue = sum(monthly_revenue)

    summary = html.Div([
        _summary_card("Profit/Unit", f"${profit:.2f}",
                      COLORS["success"] if profit > 0 else COLORS["danger"]),
        _summary_card("Margin", f"{margin:.1f}%",
                      COLORS["success"] if margin > 20 else COLORS["warning"]),
        _summary_card("Monthly Profit", f"${profit * sales:,.2f}", COLORS["primary"]),
        _summary_card("Annual Revenue", f"${annual_revenue:,.0f}", COLORS["info"]),
        _summary_card("Annual Profit", f"${annual_profit:,.0f}",
                      COLORS["success"] if annual_profit > 0 else COLORS["danger"]),
    ], className="grid-row grid-5", style={"marginTop": "20px"})

    charts = html.Div([
        html.Div([
            dcc.Graph(figure=pie_fig, config={"displayModeBar": False}),
        ], className="chart-container"),
        html.Div([
            dcc.Graph(figure=line_fig, config={"displayModeBar": False}),
        ], className="chart-container"),
    ], className="grid-row grid-2", style={"marginTop": "20px"})

    return html.Div([summary, charts])


def _summary_card(label, value, color):
    return html.Div([
        html.P(label, style={"color": COLORS["text_muted"], "fontSize": "0.8rem",
                             "marginBottom": "4px"}),
        html.H4(value, style={"fontWeight": "700", "color": color, "marginBottom": "0"}),
    ], className="dash-card", style={"textAlign": "center"})
