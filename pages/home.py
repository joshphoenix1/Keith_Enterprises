from dash import html, dcc
from config import COLORS
from components.cards import kpi_card, info_card
from utils.data import load_products, load_suppliers, load_niches, load_activity


def layout():
    products = load_products()
    suppliers = load_suppliers()
    niches = load_niches()
    activity = load_activity()

    total_products = len(products)
    total_suppliers = len(suppliers)
    total_niches = len(niches)
    avg_margin = sum(
        (p["price"] - p["cost"] - p["fba_fee"] - p["referral_fee"]) / p["price"] * 100
        for p in products
    ) / total_products if total_products else 0

    # Activity feed items
    type_icons = {
        "product": ("bi-box-seam", COLORS["primary"]),
        "supplier": ("bi-truck", COLORS["success"]),
        "niche": ("bi-graph-up", COLORS["purple"]),
        "calculator": ("bi-calculator", COLORS["warning"]),
        "risk": ("bi-shield-exclamation", COLORS["danger"]),
    }

    activity_items = []
    for a in activity:
        icon, color = type_icons.get(a["type"], ("bi-circle", COLORS["text_muted"]))
        activity_items.append(
            html.Div([
                html.Div(
                    html.I(className=f"bi {icon}", style={"color": color}),
                    className="activity-icon",
                    style={"background": f"{color}15"},
                ),
                html.Div([
                    html.Div([
                        html.Strong(a["action"],
                                    style={"color": COLORS["text"], "fontSize": "0.85rem"}),
                        html.Span(f" · {a['time']}",
                                  style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
                    ]),
                    html.P(a["detail"],
                           style={"color": COLORS["text_muted"], "fontSize": "0.8rem",
                                  "marginBottom": "0"}),
                ]),
            ], className="activity-item")
        )

    # Quick action buttons
    quick_actions = html.Div([
        dcc.Link(
            html.Button([html.I(className="bi bi-plus-circle me-2"), "Add Product"],
                        className="btn-primary-dark", style={"width": "100%", "marginBottom": "8px"}),
            href="/products",
        ),
        dcc.Link(
            html.Button([html.I(className="bi bi-calculator me-2"), "Run Calculator"],
                        className="btn-outline-dark", style={"width": "100%", "marginBottom": "8px"}),
            href="/calculator",
        ),
        dcc.Link(
            html.Button([html.I(className="bi bi-graph-up me-2"), "Explore Niches"],
                        className="btn-outline-dark", style={"width": "100%", "marginBottom": "8px"}),
            href="/niches",
        ),
        dcc.Link(
            html.Button([html.I(className="bi bi-shield-exclamation me-2"), "Risk Analysis"],
                        className="btn-outline-dark", style={"width": "100%"}),
            href="/risks",
        ),
    ], style={"display": "flex", "flexDirection": "column"})

    return html.Div([
        html.Div([
            html.H2("Dashboard"),
            html.P("Overview of your Amazon FBA feasibility research"),
        ], className="page-header"),

        # KPI Row
        html.Div([
            kpi_card("Products Tracked", str(total_products), "bi-box-seam",
                     COLORS["primary"], f"{sum(1 for p in products if p['status']=='Active')} active"),
            kpi_card("Suppliers", str(total_suppliers), "bi-truck",
                     COLORS["success"], f"{sum(1 for s in suppliers if s['verified'])} verified"),
            kpi_card("Niches Analyzed", str(total_niches), "bi-graph-up",
                     COLORS["purple"]),
            kpi_card("Avg Margin", f"{avg_margin:.1f}%", "bi-percent",
                     COLORS["warning"]),
        ], className="grid-row grid-4"),

        # Bottom row: activity + quick actions
        html.Div([
            html.Div([
                info_card("Recent Activity", html.Div(activity_items), "bi-clock-history"),
            ], style={"gridColumn": "span 2"}),
            html.Div([
                info_card("Quick Actions", quick_actions, "bi-lightning"),
            ]),
        ], className="grid-row grid-3"),
    ])
