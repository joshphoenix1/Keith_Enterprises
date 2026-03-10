from dash import html, dcc, callback, Input, Output, State
import plotly.graph_objects as go
from config import COLORS
from components.cards import info_card, kpi_card
from components.forms import styled_input, styled_dropdown, form_group
from components.charts import gauge_chart, dark_chart_layout, _hex_to_rgba
from components.pills import verdict_pill, pill
from utils.data import estimate_fba_fee, calc_referral_fee, calc_feasibility


def layout():
    categories = [
        "Kitchen & Dining", "Office Products", "Sports & Outdoors",
        "Cell Phones & Accessories", "Health & Household", "Home & Garden",
        "Tools & Home Improvement", "Toys & Games", "Beauty & Personal Care",
        "Pet Supplies", "Baby", "Grocery & Gourmet", "Automotive",
        "Patio, Lawn & Garden", "Arts, Crafts & Sewing",
    ]

    # ── Product Details Section ──
    product_form = html.Div([
        html.Div([
            html.I(className="bi bi-box-seam me-2", style={"color": COLORS["primary"]}),
            html.H6("Product Details", className="mb-0",
                     style={"color": COLORS["text"], "fontWeight": "600", "display": "inline"}),
        ], style={"marginBottom": "16px"}),
        html.Div([
            form_group("Product Name",
                       styled_input("products-name", "e.g. Silicone Spatula Set", type="text")),
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
            form_group("Monthly Sales Est.",
                       styled_input("products-sales", "500", value=500)),
        ], className="grid-row grid-4"),
    ])

    # ── Costs Section ──
    costs_form = html.Div([
        html.Div([
            html.I(className="bi bi-cash-stack me-2", style={"color": COLORS["warning"]}),
            html.H6("Costs & Fees", className="mb-0",
                     style={"color": COLORS["text"], "fontWeight": "600", "display": "inline"}),
        ], style={"marginBottom": "16px"}),
        html.Div([
            form_group("Ad Spend (% of price)",
                       styled_input("products-adspend", "10", value=10)),
            form_group("Shipping to FBA ($/unit)",
                       styled_input("products-shipping", "0.80", value=0.80)),
            form_group("Storage Cost ($/unit/mo)",
                       styled_input("products-storage", "0.15", value=0.15)),
            form_group("Other Costs ($/unit)",
                       styled_input("products-other", "0", value=0)),
        ], className="grid-row grid-4"),
    ])

    # ── Supplier Section ──
    supplier_form = html.Div([
        html.Div([
            html.I(className="bi bi-truck me-2", style={"color": COLORS["info"]}),
            html.H6("Supplier & Logistics", className="mb-0",
                     style={"color": COLORS["text"], "fontWeight": "600", "display": "inline"}),
        ], style={"marginBottom": "16px"}),
        html.Div([
            form_group("MOQ (min order qty)",
                       styled_input("products-moq", "500", value=500)),
            form_group("Lead Time (days)",
                       styled_input("products-leadtime", "20", value=20)),
            form_group("Supplier Name",
                       styled_input("products-supplier", "e.g. Shenzhen GreenTech", type="text")),
            form_group("Supplier Location",
                       styled_dropdown("products-supplier-loc",
                                       [{"label": l, "value": l} for l in [
                                           "China", "India", "Vietnam", "Turkey",
                                           "USA", "Mexico", "Other"]],
                                       "China")),
        ], className="grid-row grid-4"),
    ])

    # ── Competition Section ──
    competition_form = html.Div([
        html.Div([
            html.I(className="bi bi-people me-2", style={"color": COLORS["danger"]}),
            html.H6("Amazon Competition", className="mb-0",
                     style={"color": COLORS["text"], "fontWeight": "600", "display": "inline"}),
        ], style={"marginBottom": "16px"}),
        html.Div([
            form_group("# Competitors (page 1)",
                       styled_input("products-competitors", "15", value=15)),
            form_group("Avg Competitor Price ($)",
                       styled_input("products-avg-price", "26.99", value=26.99)),
            form_group("Avg Reviews (top 10)",
                       styled_input("products-avg-reviews", "350", value=350)),
            form_group("Avg Rating (top 10)",
                       styled_input("products-avg-rating", "4.3", value=4.3)),
        ], className="grid-row grid-4"),
        html.Div([
            form_group("Best Seller Rank (BSR)",
                       styled_input("products-bsr", "5000", value=5000)),
            form_group("Search Volume (est/mo)",
                       styled_input("products-search-vol", "15000", value=15000)),
            form_group("Amazon's Choice?",
                       styled_dropdown("products-amz-choice",
                                       [{"label": "No", "value": "no"},
                                        {"label": "Yes", "value": "yes"}],
                                       "no")),
            form_group("Patent/IP Risk",
                       styled_dropdown("products-ip-risk",
                                       [{"label": "None", "value": "none"},
                                        {"label": "Low", "value": "low"},
                                        {"label": "Medium", "value": "medium"},
                                        {"label": "High", "value": "high"}],
                                       "none")),
        ], className="grid-row grid-4"),
    ])

    return html.Div([
        html.Div([
            html.H2("Product Feasibility"),
            html.P("Full feasibility analysis — costs, competition, and market comparison"),
        ], className="page-header"),

        # Input forms
        html.Div([product_form], className="dash-card", style={"marginBottom": "16px"}),
        html.Div([costs_form], className="dash-card", style={"marginBottom": "16px"}),

        html.Div([
            html.Div([supplier_form], className="dash-card"),
            html.Div([competition_form], className="dash-card"),
        ], className="grid-row grid-2", style={"marginBottom": "20px"}),

        # Results
        html.Div(id="products-results"),
    ])


@callback(
    Output("products-results", "children"),
    Input("products-price", "value"),
    Input("products-cost", "value"),
    Input("products-weight", "value"),
    Input("products-sales", "value"),
    Input("products-category", "value"),
    Input("products-adspend", "value"),
    Input("products-other", "value"),
    Input("products-shipping", "value"),
    Input("products-storage", "value"),
    Input("products-moq", "value"),
    Input("products-leadtime", "value"),
    Input("products-competitors", "value"),
    Input("products-avg-price", "value"),
    Input("products-avg-reviews", "value"),
    Input("products-avg-rating", "value"),
    Input("products-bsr", "value"),
    Input("products-search-vol", "value"),
    Input("products-amz-choice", "value"),
    Input("products-ip-risk", "value"),
)
def update_feasibility(price, cost, weight, sales, category, adspend, other,
                       shipping, storage, moq, leadtime,
                       competitors, avg_price, avg_reviews, avg_rating,
                       bsr, search_vol, amz_choice, ip_risk):
    price = float(price or 0)
    cost = float(cost or 0)
    weight = float(weight or 0)
    sales = int(sales or 0)
    adspend_pct = float(adspend or 0) / 100
    other = float(other or 0)
    shipping = float(shipping or 0)
    storage = float(storage or 0)
    moq = int(moq or 0)
    leadtime = int(leadtime or 0)
    competitors = int(competitors or 0)
    avg_price = float(avg_price or 0)
    avg_reviews = int(avg_reviews or 0)
    avg_rating = float(avg_rating or 0)
    bsr = int(bsr or 0)
    search_vol = int(search_vol or 0)

    if price <= 0 or cost <= 0:
        return html.P("Enter valid price and cost to see results.",
                      style={"color": COLORS["text_muted"], "padding": "40px", "textAlign": "center"})

    fba_fee = estimate_fba_fee(weight)
    referral_fee = calc_referral_fee(price, category)
    r = calc_feasibility(
        price, cost, fba_fee, referral_fee, sales, adspend_pct, other,
        num_competitors=competitors, avg_reviews=avg_reviews,
        avg_rating=avg_rating, avg_competitor_price=avg_price,
        bsr=bsr, moq=moq, lead_time=leadtime,
        shipping_cost=shipping, storage_cost=storage,
    )

    verdict = verdict_pill(r["verdict"])

    # ── Gauge + Verdict ──
    gauge = dcc.Graph(figure=gauge_chart(r["score"], "Feasibility Score"),
                      config={"displayModeBar": False},
                      style={"height": "220px"})

    # ── KPI Row ──
    profit_color = COLORS["success"] if r["profit_per_unit"] > 0 else COLORS["danger"]
    margin_color = COLORS["success"] if r["margin"] > 20 else COLORS["warning"] if r["margin"] > 10 else COLORS["danger"]

    kpi_row = html.Div([
        kpi_card("Revenue/mo", f"${r['revenue']:,.0f}", "bi-graph-up-arrow", COLORS["primary"]),
        kpi_card("Profit/Unit", f"${r['profit_per_unit']:.2f}", "bi-currency-dollar", profit_color),
        kpi_card("Margin", f"{r['margin']:.1f}%", "bi-percent", margin_color),
        kpi_card("Monthly Profit", f"${r['monthly_profit']:,.0f}", "bi-cash-coin",
                 COLORS["success"] if r["monthly_profit"] > 0 else COLORS["danger"]),
        kpi_card("Annual Profit", f"${r['annual_profit']:,.0f}", "bi-calendar-check",
                 COLORS["success"] if r["annual_profit"] > 0 else COLORS["danger"]),
        kpi_card("ROI", f"{r['roi']:.0f}%", "bi-arrow-return-right",
                 COLORS["success"] if r["roi"] > 50 else COLORS["warning"]),
    ], className="grid-row grid-3", style={"marginBottom": "20px"})

    # ── Cost Breakdown ──
    cost_section = info_card("Cost Breakdown (per unit)", html.Div([
        _cost_row("Product Cost", f"${cost:.2f}"),
        _cost_row("FBA Fulfillment Fee", f"${fba_fee:.2f}"),
        _cost_row("Referral Fee ({:.0f}%)".format(referral_fee / price * 100 if price else 0),
                  f"${referral_fee:.2f}"),
        _cost_row("Shipping to FBA", f"${shipping:.2f}"),
        _cost_row("Storage Cost", f"${storage:.2f}"),
        _cost_row("Ad Spend ({:.0f}%)".format(adspend_pct * 100), f"${r['ad_spend_per_unit']:.2f}"),
        _cost_row("Other Costs", f"${other:.2f}"),
        html.Hr(style={"borderColor": COLORS["card_border"]}),
        _cost_row("Total Cost/Unit", f"${r['total_cost_per_unit']:.2f}", bold=True),
        _cost_row("Selling Price", f"${price:.2f}", bold=True,
                  color=COLORS["primary"]),
        _cost_row("Profit/Unit", f"${r['profit_per_unit']:.2f}", bold=True,
                  color=COLORS["success"] if r["profit_per_unit"] > 0 else COLORS["danger"]),
    ]), "bi-receipt")

    # ── Investment & Breakeven ──
    invest_section = info_card("Investment Analysis", html.Div([
        _cost_row("Initial Investment (MOQ)", f"${r['initial_investment']:,.0f}"),
        _cost_row("MOQ", f"{moq:,} units"),
        _cost_row("Lead Time", f"{leadtime} days"),
        _cost_row("Breakeven Units", f"{r['breakeven_units']:,}"),
        _cost_row("Breakeven Months",
                  f"{r['breakeven_units'] / sales:.1f}" if sales > 0 else "—"),
        html.Hr(style={"borderColor": COLORS["card_border"]}),
        _cost_row("Monthly Revenue", f"${r['revenue']:,.0f}"),
        _cost_row("Monthly Profit", f"${r['monthly_profit']:,.0f}",
                  color=COLORS["success"] if r["monthly_profit"] > 0 else COLORS["danger"]),
        _cost_row("Annual Profit", f"${r['annual_profit']:,.0f}", bold=True,
                  color=COLORS["success"] if r["annual_profit"] > 0 else COLORS["danger"]),
    ]), "bi-piggy-bank")

    # ── Competition Analysis ──
    comp_items = []
    if competitors > 0:
        # Competition level
        if competitors <= 5:
            comp_level, comp_color = "Low", COLORS["success"]
        elif competitors <= 15:
            comp_level, comp_color = "Medium", COLORS["warning"]
        elif competitors <= 30:
            comp_level, comp_color = "High", COLORS["danger"]
        else:
            comp_level, comp_color = "Very High", COLORS["danger"]

        comp_items.append(_comp_row("Competition Level", comp_level, comp_color))
        comp_items.append(_comp_row("Competitors (page 1)", str(competitors)))

        # Price positioning
        if avg_price > 0:
            diff = price - avg_price
            diff_pct = (diff / avg_price) * 100
            if diff < 0:
                pos_text = f"${abs(diff):.2f} below avg ({abs(diff_pct):.0f}% cheaper)"
                pos_color = COLORS["success"]
            elif diff > 0:
                pos_text = f"${diff:.2f} above avg ({diff_pct:.0f}% more)"
                pos_color = COLORS["warning"]
            else:
                pos_text = "At market average"
                pos_color = COLORS["info"]
            comp_items.append(_comp_row("Price Position", pos_text, pos_color))
            comp_items.append(_comp_row("Avg Competitor Price", f"${avg_price:.2f}"))

        # Review barrier
        if avg_reviews > 0:
            if avg_reviews > 1000:
                rev_text, rev_color = f"{avg_reviews:,} — very hard to compete", COLORS["danger"]
            elif avg_reviews > 500:
                rev_text, rev_color = f"{avg_reviews:,} — difficult entry", COLORS["warning"]
            elif avg_reviews > 100:
                rev_text, rev_color = f"{avg_reviews:,} — moderate barrier", COLORS["info"]
            else:
                rev_text, rev_color = f"{avg_reviews:,} — easy entry", COLORS["success"]
            comp_items.append(_comp_row("Review Barrier", rev_text, rev_color))

        if avg_rating > 0:
            rat_color = COLORS["success"] if avg_rating < 4.2 else COLORS["warning"] if avg_rating < 4.5 else COLORS["danger"]
            comp_items.append(_comp_row("Avg Rating", f"{avg_rating:.1f} ★", rat_color))

    if bsr > 0:
        if bsr < 5000:
            bsr_text = f"#{bsr:,} — excellent demand"
            bsr_color = COLORS["success"]
        elif bsr < 20000:
            bsr_text = f"#{bsr:,} — good demand"
            bsr_color = COLORS["info"]
        elif bsr < 50000:
            bsr_text = f"#{bsr:,} — moderate demand"
            bsr_color = COLORS["warning"]
        else:
            bsr_text = f"#{bsr:,} — low demand"
            bsr_color = COLORS["danger"]
        comp_items.append(_comp_row("Best Seller Rank", bsr_text, bsr_color))

    if search_vol > 0:
        comp_items.append(_comp_row("Search Volume", f"{search_vol:,}/mo"))

    if amz_choice == "yes":
        comp_items.append(_comp_row("Amazon's Choice", "Yes — harder to compete", COLORS["warning"]))

    if ip_risk != "none":
        risk_colors = {"low": COLORS["info"], "medium": COLORS["warning"], "high": COLORS["danger"]}
        comp_items.append(_comp_row("Patent/IP Risk", ip_risk.title(), risk_colors.get(ip_risk, COLORS["text_muted"])))

    if not comp_items:
        comp_items.append(html.P("Enter competition data above for analysis.",
                                 style={"color": COLORS["text_muted"], "fontSize": "0.85rem"}))

    comp_section = info_card("Competition Analysis", html.Div(comp_items), "bi-people")

    # ── Score Breakdown Chart ──
    # Show what contributes to the score
    score_breakdown = _build_score_breakdown(r, competitors, avg_reviews, avg_price, price, sales)

    return html.Div([
        # Gauge + verdict row
        html.Div([
            html.Div([
                info_card("Feasibility Score", html.Div([
                    gauge,
                    html.Div(verdict, style={"textAlign": "center", "marginTop": "8px"}),
                ]), "bi-speedometer2"),
            ]),
            html.Div([score_breakdown]),
        ], className="grid-row grid-2", style={"marginBottom": "20px"}),

        # KPIs
        kpi_row,

        # Details grid
        html.Div([
            html.Div([cost_section]),
            html.Div([invest_section]),
            html.Div([comp_section]),
        ], className="grid-row grid-3"),
    ])


def _cost_row(label, value, bold=False, color=None):
    weight = "600" if bold else "400"
    return html.Div([
        html.Span(label, style={"color": COLORS["text_muted"] if not bold else COLORS["text"],
                                "fontWeight": weight, "fontSize": "0.85rem"}),
        html.Span(value, style={"color": color or COLORS["text"], "fontWeight": weight,
                                "fontSize": "0.85rem"}),
    ], style={"display": "flex", "justifyContent": "space-between", "padding": "5px 0"})


def _comp_row(label, value, color=None):
    return html.Div([
        html.Span(label, style={"color": COLORS["text_muted"], "fontSize": "0.85rem"}),
        html.Span(value, style={
            "color": color or COLORS["text"], "fontSize": "0.85rem", "fontWeight": "500",
        }),
    ], style={"display": "flex", "justifyContent": "space-between", "padding": "5px 0",
              "borderBottom": f"1px solid {COLORS['card_border']}"})


def _build_score_breakdown(r, competitors, avg_reviews, avg_price, price, sales):
    """Build a horizontal bar chart showing score components."""
    # Recalculate individual component scores
    margin = r["margin"]
    roi = r["roi"]
    monthly_profit = r["monthly_profit"]

    components = {}

    # Margin (max 20)
    if margin > 30: components["Margin"] = 20
    elif margin > 20: components["Margin"] = 14
    elif margin > 10: components["Margin"] = 8
    else: components["Margin"] = 3

    # ROI (max 20)
    if roi > 100: components["ROI"] = 20
    elif roi > 50: components["ROI"] = 14
    elif roi > 25: components["ROI"] = 8
    else: components["ROI"] = 3

    # Profit (max 20)
    if monthly_profit > 3000: components["Profit"] = 20
    elif monthly_profit > 1500: components["Profit"] = 14
    elif monthly_profit > 500: components["Profit"] = 8
    else: components["Profit"] = 3

    # Volume (max 15)
    if sales > 500: components["Volume"] = 15
    elif sales > 200: components["Volume"] = 10
    elif sales > 50: components["Volume"] = 5
    else: components["Volume"] = 0

    # Competition (max 15)
    comp_score = 8
    if competitors > 0:
        if competitors <= 5: comp_score = 15
        elif competitors <= 15: comp_score = 10
        elif competitors <= 30: comp_score = 5
        else: comp_score = 2
        if avg_reviews > 1000: comp_score -= 5
        elif avg_reviews > 500: comp_score -= 3
        elif avg_reviews < 100: comp_score += 3
    components["Competition"] = max(0, comp_score)

    # Price (max 10)
    price_score = 5
    if avg_price > 0 and price > 0:
        ratio = price / avg_price
        if 0.85 <= ratio <= 1.0: price_score = 10
        elif 0.7 <= ratio < 0.85: price_score = 7
        elif 1.0 < ratio <= 1.15: price_score = 6
        else: price_score = 3
    components["Price Fit"] = price_score

    max_scores = {"Margin": 20, "ROI": 20, "Profit": 20, "Volume": 15,
                  "Competition": 15, "Price Fit": 10}

    labels = list(components.keys())
    values = list(components.values())
    maxes = [max_scores[k] for k in labels]
    colors = [COLORS["success"] if v >= m * 0.7 else COLORS["warning"] if v >= m * 0.4
              else COLORS["danger"] for v, m in zip(values, maxes)]

    fig = go.Figure()
    # Background bars (max)
    fig.add_trace(go.Bar(
        y=labels, x=maxes, orientation="h",
        marker_color=_hex_to_rgba(COLORS['card_border'], 0.37),
        hoverinfo="skip", showlegend=False,
    ))
    # Actual score bars
    fig.add_trace(go.Bar(
        y=labels, x=values, orientation="h",
        marker_color=colors,
        text=[f"{v}/{m}" for v, m in zip(values, maxes)],
        textposition="inside",
        textfont=dict(color="white", size=11),
        hovertemplate="%{y}: %{x}/%{customdata}<extra></extra>",
        customdata=maxes,
        showlegend=False,
    ))

    layout_kwargs = dark_chart_layout("Score Breakdown", height=260, showlegend=False)
    layout_kwargs["margin"] = dict(l=80, r=20, t=40, b=20)
    layout_kwargs["yaxis"] = dict(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    layout_kwargs["xaxis"] = dict(visible=False, gridcolor="rgba(0,0,0,0)")
    fig.update_layout(barmode="overlay", **layout_kwargs)

    return info_card("Score Breakdown", dcc.Graph(
        figure=fig, config={"displayModeBar": False},
    ), "bi-bar-chart-steps")
