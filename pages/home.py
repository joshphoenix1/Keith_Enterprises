import json
import os
from dash import html, dcc
from config import COLORS
from components.cards import kpi_card, info_card

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def _load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return [] if filename != "inbox.json" else {"messages": []}


def layout():
    offers = _load_json("offers.json")
    buyers = _load_json("buyers.json")
    activity = _load_json("activity.json")
    inbox = _load_json("inbox.json")
    messages = inbox.get("messages", []) if isinstance(inbox, dict) else []

    total_offers = len(offers)
    new_offers = sum(1 for o in offers if o.get("status") == "new")
    matched_offers = sum(1 for o in offers if o.get("status") == "matched")
    accepted_offers = sum(1 for o in offers if o.get("status") == "accepted")
    total_buyers = len(buyers)
    unread_msgs = sum(1 for m in messages if not m.get("read"))

    # Calculate today's offer value
    from datetime import datetime
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_value = sum(
        o.get("offered_price", 0) * o.get("quantity", 0)
        for o in offers if o.get("created_at", "").startswith(today_str)
    )

    # Activity feed
    type_icons = {
        "offer": ("bi-tag", COLORS["primary"]),
        "match": ("bi-link-45deg", COLORS["purple"]),
        "buyer": ("bi-person-plus", COLORS["success"]),
        "inbox": ("bi-chat-left-text", COLORS["info"]),
    }

    activity_items = []
    for a in activity:
        icon, color = type_icons.get(a.get("type", ""), ("bi-circle", COLORS["text_muted"]))
        activity_items.append(
            html.Div([
                html.Div(
                    html.I(className=f"bi {icon}", style={"color": color}),
                    style={
                        "width": "36px", "height": "36px", "borderRadius": "10px",
                        "background": f"{color}15", "display": "flex",
                        "alignItems": "center", "justifyContent": "center",
                        "flexShrink": "0",
                    },
                ),
                html.Div([
                    html.Div([
                        html.Strong(a.get("action", ""),
                                    style={"color": COLORS["text"], "fontSize": "0.85rem"}),
                        html.Span(f" · {a.get('time', '')}",
                                  style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
                    ]),
                    html.P(a.get("detail", ""),
                           style={"color": COLORS["text_muted"], "fontSize": "0.8rem",
                                  "marginBottom": "0"}),
                ]),
            ], style={"display": "flex", "gap": "12px", "alignItems": "center",
                       "padding": "10px 0",
                       "borderBottom": f"1px solid {COLORS['card_border']}"})
        )

    # WhatsApp status
    wa_status = ""
    try:
        from utils.whatsapp import test_connection
        wa_result = test_connection()
        if wa_result.get("connected"):
            wa_phone = wa_result.get("phone_number", "")
            wa_status = html.Div([
                html.I(className="bi bi-whatsapp me-2", style={"color": "#25D366"}),
                html.Span("WhatsApp Connected", style={"color": "#25D366", "fontWeight": "600",
                                                        "fontSize": "0.8rem"}),
                html.Span(f" (+{wa_phone})" if wa_phone else "",
                          style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
            ], style={"padding": "8px 14px", "background": "#25D36612",
                      "borderRadius": "8px", "marginBottom": "8px"})
        else:
            wa_status = html.Div([
                html.I(className="bi bi-whatsapp me-2", style={"color": COLORS["text_muted"]}),
                html.Span("WhatsApp Disconnected", style={"color": COLORS["text_muted"],
                                                           "fontSize": "0.8rem"}),
            ], style={"padding": "8px 14px", "background": f"{COLORS['card_border']}30",
                      "borderRadius": "8px", "marginBottom": "8px"})
    except Exception:
        pass

    # Quick actions
    quick_actions = html.Div([
        wa_status,
        dcc.Link(
            html.Button([html.I(className="bi bi-chat-left-text me-2"), f"Inbox ({unread_msgs} unread)"],
                        className="btn-primary-dark", style={"width": "100%", "marginBottom": "8px"}),
            href="/inbox",
        ),
        dcc.Link(
            html.Button([html.I(className="bi bi-plus-circle me-2"), "Add Offer"],
                        className="btn-outline-dark", style={"width": "100%", "marginBottom": "8px"}),
            href="/offers",
        ),
        dcc.Link(
            html.Button([html.I(className="bi bi-people me-2"), "Manage Buyers"],
                        className="btn-outline-dark", style={"width": "100%", "marginBottom": "8px"}),
            href="/buyers",
        ),
        dcc.Link(
            html.Button([html.I(className="bi bi-camera me-2"), "Scan Product"],
                        className="btn-outline-dark", style={"width": "100%"}),
            href="/scanner",
        ),
    ], style={"display": "flex", "flexDirection": "column"})

    # Offer pipeline summary
    pipeline_data = [
        ("New", new_offers, COLORS["info"]),
        ("Evaluating", sum(1 for o in offers if o.get("status") == "evaluating"), COLORS["warning"]),
        ("Matched", matched_offers, COLORS["purple"]),
        ("Accepted", accepted_offers, COLORS["success"]),
        ("Rejected", sum(1 for o in offers if o.get("status") == "rejected"), COLORS["danger"]),
    ]

    pipeline_bars = html.Div([
        html.Div([
            html.Div([
                html.Span(label, style={"color": COLORS["text_muted"], "fontSize": "0.75rem",
                                        "minWidth": "80px"}),
                html.Div(
                    style={
                        "flex": "1", "height": "8px", "borderRadius": "4px",
                        "background": COLORS["card_border"], "overflow": "hidden",
                    },
                    children=html.Div(style={
                        "width": f"{min(count / max(total_offers, 1) * 100, 100)}%",
                        "height": "100%", "background": color, "borderRadius": "4px",
                    }),
                ),
                html.Span(str(count), style={"color": color, "fontWeight": "700",
                                              "fontSize": "0.85rem", "minWidth": "30px",
                                              "textAlign": "right"}),
            ], style={"display": "flex", "gap": "12px", "alignItems": "center",
                       "marginBottom": "8px"})
        ]) for label, count, color in pipeline_data
    ])

    return html.Div([
        html.Div([
            html.H2("Dashboard"),
            html.P("Inventory offer intake, evaluation, and buyer matching"),
        ], className="page-header"),

        # KPI Row
        html.Div([
            kpi_card("Total Offers", str(total_offers), "bi-tag",
                     COLORS["primary"], f"{new_offers} new today"),
            kpi_card("Matched", str(matched_offers), "bi-link-45deg",
                     COLORS["purple"], f"{accepted_offers} accepted"),
            kpi_card("Buyers", str(total_buyers), "bi-people",
                     COLORS["success"]),
            kpi_card("Today's Value", f"${today_value:,.0f}", "bi-currency-dollar",
                     COLORS["warning"]),
        ], className="grid-row grid-4"),

        # Bottom row: pipeline + activity + quick actions
        html.Div([
            html.Div([
                info_card("Offer Pipeline", pipeline_bars, "bi-funnel"),
            ]),
            html.Div([
                info_card("Recent Activity", html.Div(activity_items), "bi-clock-history"),
            ]),
            html.Div([
                info_card("Quick Actions", quick_actions, "bi-lightning"),
            ]),
        ], className="grid-row grid-3"),
    ])
