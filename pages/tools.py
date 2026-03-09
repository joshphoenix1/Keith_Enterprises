from dash import html
from config import COLORS
from components.cards import info_card


def layout():
    # ── Seller Assistant Details (our chosen tool) ──
    sa_features = [
        ("Chrome Extension", True),
        ("Bulk List Scanning", "Up to 150K/mo (Business)"),
        ("IP Complaint Alerts", "Proprietary DB — type, dates, filings"),
        ("Brand Analyzer", True),
        ("Seller Spy (competitor tracking)", True),
        ("Bulk Restriction Checker", "Thousands of ASINs at once"),
        ("Built-in VPN", "Included free"),
        ("API / Zapier / Make", "Business+ plans"),
        ("Team / VA Management", True),
        ("Keepa Integration", True),
        ("ROI / Profit Calculator", True),
        ("Buy Box Analysis", True),
        ("Human Support", "~2hr response time"),
    ]

    sa_plans = [
        {"plan": "Start", "monthly": "Annual only", "annual": "$13.33/mo ($159.99/yr)",
         "limits": "3,500 lookups/mo, 3 Google Sheets"},
        {"plan": "Pro", "monthly": "$29.99/mo", "annual": "$24.99/mo ($299.99/yr)",
         "limits": "10K lookups/mo, 2 seats, IP-Alert, VPN"},
        {"plan": "Business", "monthly": "$79.99/mo", "annual": "$69.99/mo ($839.88/yr)",
         "limits": "150K scans/mo, Price List Analyzer, Bulk Restriction Checker, Zapier/Make"},
        {"plan": "Business Plus", "monthly": "$189.99/mo", "annual": "$159.99/mo ($1,919.88/yr)",
         "limits": "5 seats, unlimited features"},
        {"plan": "Agency", "monthly": "From $399.99/mo", "annual": "Annual contract",
         "limits": "Unlimited seats/workspaces, dedicated CSM, SLA, SSO"},
    ]

    pros = [
        "Bulk sourcing capability: Price List Analyzer for wholesale lists",
        "Superior IP alerts: Proprietary database with violation type, dates, and filing details",
        "Brand Analyzer & Seller Spy: Competitive intelligence tools",
        "Bulk Restriction Checker: Check thousands of ASINs at once",
        "Built-in VPN: Useful for VAs and international sellers; included free",
        "API + Zapier/Make: Superior integration and automation options",
        "Better support: Human support with ~2hr response time",
        "Team management: Multi-seat plans with VA account controls",
    ]

    cons = [
        "No mobile app: No mobile support — need separate tool for in-store retail arbitrage",
        "Higher cost for bulk tools: Business plan at $70–80/mo",
        "Learning curve: More features means more UI complexity",
        "Annual lock-in for cheapest tier: Start plan requires annual commitment",
    ]

    # ── Feature table ──
    feature_rows = []
    for name, val in sa_features:
        if val is True:
            display = html.I(className="bi bi-check-circle-fill",
                            style={"color": COLORS["success"], "fontSize": "1rem"})
        else:
            display = html.Span(str(val), style={"color": COLORS["text_muted"], "fontSize": "0.85rem"})
        feature_rows.append(
            html.Tr([
                html.Td(name, style={"padding": "10px 16px", "color": COLORS["text"],
                                     "borderBottom": f"1px solid {COLORS['card_border']}"}),
                html.Td(display, style={"padding": "10px 16px", "textAlign": "center",
                                        "borderBottom": f"1px solid {COLORS['card_border']}"}),
            ])
        )

    feature_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Feature", style={"padding": "10px 16px", "textAlign": "left"}),
            html.Th("Status", style={"padding": "10px 16px", "textAlign": "center"}),
        ], style={"backgroundColor": COLORS["sidebar"],
                  "borderBottom": f"1px solid {COLORS['card_border']}"})),
        html.Tbody(feature_rows),
    ], style={"width": "100%", "borderCollapse": "collapse", "fontSize": "0.85rem"})

    # ── Pricing table ──
    pricing_rows = []
    for p in sa_plans:
        pricing_rows.append(
            html.Tr([
                html.Td(html.Strong(p["plan"]),
                        style={"padding": "10px 16px", "color": COLORS["text"],
                               "borderBottom": f"1px solid {COLORS['card_border']}"}),
                html.Td(p["monthly"], style={"padding": "10px 16px", "color": COLORS["text_muted"],
                                             "borderBottom": f"1px solid {COLORS['card_border']}"}),
                html.Td(p["annual"], style={"padding": "10px 16px", "color": COLORS["primary"],
                                            "fontWeight": "600",
                                            "borderBottom": f"1px solid {COLORS['card_border']}"}),
                html.Td(p["limits"], style={"padding": "10px 16px", "color": COLORS["text_muted"],
                                            "fontSize": "0.8rem",
                                            "borderBottom": f"1px solid {COLORS['card_border']}"}),
            ])
        )

    pricing_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Plan", style={"padding": "10px 16px", "textAlign": "left"}),
            html.Th("Monthly", style={"padding": "10px 16px", "textAlign": "left"}),
            html.Th("Annual", style={"padding": "10px 16px", "textAlign": "left"}),
            html.Th("Key Limits", style={"padding": "10px 16px", "textAlign": "left"}),
        ], style={"backgroundColor": COLORS["sidebar"],
                  "borderBottom": f"1px solid {COLORS['card_border']}"})),
        html.Tbody(pricing_rows),
    ], style={"width": "100%", "borderCollapse": "collapse", "fontSize": "0.85rem"})

    # ── Pros / Cons ──
    pros_section = html.Div([
        html.Div([
            html.I(className="bi bi-check-circle-fill me-2",
                   style={"color": COLORS["success"], "flexShrink": "0"}),
            html.Span(p, style={"color": COLORS["text"], "fontSize": "0.85rem"}),
        ], style={"display": "flex", "alignItems": "flex-start", "marginBottom": "8px"})
        for p in pros
    ])

    cons_section = html.Div([
        html.Div([
            html.I(className="bi bi-exclamation-triangle-fill me-2",
                   style={"color": COLORS["warning"], "flexShrink": "0"}),
            html.Span(c, style={"color": COLORS["text"], "fontSize": "0.85rem"}),
        ], style={"display": "flex", "alignItems": "flex-start", "marginBottom": "8px"})
        for c in cons
    ])

    # ── Comparison note vs SellerAmp ──
    comparison_note = html.Div([
        html.Div([
            html.I(className="bi bi-info-circle me-2", style={"color": COLORS["info"]}),
            html.Strong("Decision: ", style={"color": COLORS["text"]}),
            html.Span("Seller Assistant selected over SellerAmp SAS. ",
                      style={"color": COLORS["text_muted"]}),
            html.Span("SellerAmp's only real edge is a mobile app with barcode scanning for "
                      "in-store retail arbitrage. For wholesale & online arbitrage, "
                      "Seller Assistant is the clear upgrade.",
                      style={"color": COLORS["text_muted"]}),
        ], style={"fontSize": "0.85rem"}),
    ], style={
        "background": f"{COLORS['info']}10", "padding": "16px",
        "borderRadius": "8px", "marginBottom": "20px",
    })

    # ── Integration status ──
    integration_badge = html.Div([
        html.Div([
            html.Div([
                html.I(className="bi bi-plug-fill",
                       style={"fontSize": "1.2rem", "color": COLORS["success"]}),
            ], style={
                "width": "40px", "height": "40px", "borderRadius": "10px",
                "background": f"{COLORS['success']}15", "display": "flex",
                "alignItems": "center", "justifyContent": "center",
            }),
            html.Div([
                html.Strong("API Integration Available",
                            style={"color": COLORS["text"], "fontSize": "0.9rem"}),
                html.P("Connect via API key on the Accounts page for automated data ingestion",
                       style={"color": COLORS["text_muted"], "fontSize": "0.8rem",
                              "marginBottom": "0"}),
            ]),
        ], style={"display": "flex", "gap": "12px", "alignItems": "center"}),
    ], style={
        "background": f"{COLORS['success']}08", "border": f"1px solid {COLORS['success']}30",
        "padding": "16px", "borderRadius": "8px", "marginBottom": "20px",
    })

    return html.Div([
        html.Div([
            html.Div([
                html.H2("Seller Assistant"),
                html.Span("SELECTED", style={
                    "background": f"{COLORS['success']}20", "color": COLORS["success"],
                    "padding": "4px 12px", "borderRadius": "20px", "fontSize": "0.75rem",
                    "fontWeight": "700", "marginLeft": "12px", "verticalAlign": "middle",
                }),
            ], style={"display": "flex", "alignItems": "center"}),
            html.P("Our primary Amazon seller research and sourcing tool"),
        ], className="page-header"),

        comparison_note,
        integration_badge,

        html.Div([
            html.Div([
                info_card("Features", feature_table, "bi-list-check"),
            ]),
            html.Div([
                info_card("Pricing Plans", pricing_table, "bi-currency-dollar"),
            ]),
        ], className="grid-row grid-2"),

        html.Div([
            html.Div([
                info_card("Advantages", pros_section, "bi-hand-thumbs-up"),
            ]),
            html.Div([
                info_card("Limitations", cons_section, "bi-exclamation-triangle"),
            ]),
        ], className="grid-row grid-2", style={"marginTop": "20px"}),
    ])
