from dash import html, dcc, callback, Input, Output, State
import plotly.graph_objects as go
from config import COLORS
from components.cards import info_card
from components.forms import styled_input, styled_dropdown, form_group
from components.charts import gauge_chart
from components.pills import verdict_pill
from utils.data import estimate_fba_fee, calc_referral_fee, calc_feasibility


def layout():
    categories = [
        "Kitchen & Dining", "Office Products", "Sports & Outdoors",
        "Cell Phones & Accessories", "Health & Household", "Home & Garden",
        "Tools & Home Improvement", "Toys & Games",
    ]

    form = html.Div([
        html.Div([
            form_group("Product Name",
                       styled_input("products-name", "e.g. Silicone Spatula Set",
                                    type="text")),
            form_group("Category",
                       styled_dropdown("products-category",
                                       [{"label": c, "value": c} for c in categories],
                                       categories[0])),
        ], className="grid-row grid-2"),
        html.Div([
            form_group("Selling Price ($)",
                       styled_input("products-price", "24.99", value=24.99)),
            form_group("Product Cost ($)",
                       styled_input("products-cost", "4.50", value=4.50)),
            form_group("Weight (lb)",
                       styled_input("products-weight", "1.2", value=1.2)),
            form_group("Monthly Sales (units)",
                       styled_input("products-sales", "500", value=500)),
        ], className="grid-row grid-4"),
        html.Div([
            form_group("Ad Spend (%)",
                       styled_input("products-adspend", "10", value=10)),
            form_group("Other Costs ($)",
                       styled_input("products-other", "0", value=0)),
        ], className="grid-row grid-2"),
    ])

    return html.Div([
        html.Div([
            html.H2("Product Feasibility"),
            html.P("Enter product details for real-time feasibility analysis"),
        ], className="page-header"),

        html.Div([
            html.Div([
                info_card("Product Details", form, "bi-box-seam"),
            ], style={"gridColumn": "span 2"}),
            html.Div([
                info_card("Feasibility Score",
                          html.Div(id="products-gauge-container"), "bi-speedometer2"),
            ]),
        ], className="grid-row grid-3"),

        html.Div(id="products-results"),
    ])


@callback(
    Output("products-gauge-container", "children"),
    Output("products-results", "children"),
    Input("products-price", "value"),
    Input("products-cost", "value"),
    Input("products-weight", "value"),
    Input("products-sales", "value"),
    Input("products-category", "value"),
    Input("products-adspend", "value"),
    Input("products-other", "value"),
)
def update_feasibility(price, cost, weight, sales, category, adspend, other):
    price = float(price or 0)
    cost = float(cost or 0)
    weight = float(weight or 0)
    sales = int(sales or 0)
    adspend_pct = float(adspend or 0) / 100
    other = float(other or 0)

    if price <= 0 or cost <= 0:
        return html.P("Enter valid price and cost", style={"color": COLORS["text_muted"]}), ""

    fba_fee = estimate_fba_fee(weight)
    referral_fee = calc_referral_fee(price, category)
    result = calc_feasibility(price, cost, fba_fee, referral_fee, sales, adspend_pct, other)

    gauge = dcc.Graph(figure=gauge_chart(result["score"], "Feasibility Score"),
                      config={"displayModeBar": False},
                      style={"height": "220px"})
    verdict = verdict_pill(result["verdict"])

    results_cards = html.Div([
        html.Div([
            _metric_card("Revenue/mo", f"${result['revenue']:,.2f}", COLORS["primary"]),
            _metric_card("Profit/Unit", f"${result['profit_per_unit']:.2f}",
                         COLORS["success"] if result["profit_per_unit"] > 0 else COLORS["danger"]),
            _metric_card("Margin", f"{result['margin']:.1f}%",
                         COLORS["success"] if result["margin"] > 20 else COLORS["warning"]),
            _metric_card("Monthly Profit", f"${result['monthly_profit']:,.2f}",
                         COLORS["success"] if result["monthly_profit"] > 0 else COLORS["danger"]),
            _metric_card("ROI", f"{result['roi']:.1f}%",
                         COLORS["success"] if result["roi"] > 50 else COLORS["warning"]),
        ], className="grid-row grid-5"),
        html.Div([
            info_card("Cost Breakdown", html.Div([
                _cost_row("Product Cost", f"${cost:.2f}"),
                _cost_row("FBA Fee", f"${fba_fee:.2f}"),
                _cost_row("Referral Fee", f"${referral_fee:.2f}"),
                _cost_row("Ad Spend", f"${result['ad_spend_per_unit']:.2f}"),
                _cost_row("Other Costs", f"${other:.2f}"),
                html.Hr(style={"borderColor": COLORS["card_border"]}),
                _cost_row("Total Cost/Unit", f"${result['total_cost_per_unit']:.2f}", bold=True),
                _cost_row("Selling Price", f"${price:.2f}", bold=True),
            ]), "bi-receipt"),
        ]),
    ])

    return html.Div([gauge, html.Div(verdict, style={"textAlign": "center", "marginTop": "8px"})]), results_cards


def _metric_card(label, value, color):
    return html.Div([
        html.P(label, style={"color": COLORS["text_muted"], "fontSize": "0.8rem",
                             "marginBottom": "4px"}),
        html.H4(value, style={"fontWeight": "700", "color": color, "marginBottom": "0"}),
    ], className="dash-card", style={"textAlign": "center"})


def _cost_row(label, value, bold=False):
    weight = "600" if bold else "400"
    return html.Div([
        html.Span(label, style={"color": COLORS["text_muted"] if not bold else COLORS["text"],
                                "fontWeight": weight}),
        html.Span(value, style={"color": COLORS["text"], "fontWeight": weight}),
    ], style={"display": "flex", "justifyContent": "space-between", "padding": "6px 0",
              "fontSize": "0.85rem"})
