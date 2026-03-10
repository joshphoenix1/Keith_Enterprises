import json
import os
from datetime import datetime

from dash import html, dcc, callback, Input, Output, State, no_update

from config import COLORS
from components.cards import kpi_card, info_card
from components.forms import styled_input, styled_dropdown, form_group
from components.pills import pill
from components.tables import dark_table

# ---------------------------------------------------------------------------
# Data paths
# ---------------------------------------------------------------------------
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
BUYERS_PATH = os.path.join(_DATA_DIR, "buyers.json")
OFFERS_PATH = os.path.join(_DATA_DIR, "offers.json")

# ---------------------------------------------------------------------------
# Category color mapping
# ---------------------------------------------------------------------------
CATEGORY_COLORS = {
    "OTC": COLORS["success"],
    "HBA": COLORS["info"],
    "Toys": COLORS["warning"],
    "Tools": COLORS["text_muted"],
    "Electronics": COLORS["primary"],
    "Grocery": COLORS["success"],
    "Household": COLORS["purple"],
    "Apparel": COLORS["danger"],
    "Other": COLORS["text_muted"],
}

ALL_CATEGORIES = list(CATEGORY_COLORS.keys())


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------
def _load_buyers():
    if not os.path.exists(BUYERS_PATH):
        return []
    with open(BUYERS_PATH) as f:
        return json.load(f)


def _save_buyers(buyers):
    with open(BUYERS_PATH, "w") as f:
        json.dump(buyers, f, indent=2)


def _load_offers():
    if not os.path.exists(OFFERS_PATH):
        return []
    with open(OFFERS_PATH) as f:
        return json.load(f)


def _save_offers(offers):
    with open(OFFERS_PATH, "w") as f:
        json.dump(offers, f, indent=2)


# ---------------------------------------------------------------------------
# Matching algorithm
# ---------------------------------------------------------------------------
def match_buyers(offer, buyers):
    """Score each buyer against an offer. Returns sorted list of dicts."""
    results = []
    for buyer in buyers:
        score = 0
        # Category match (0-50 points)
        if offer.get("category") and offer["category"] in buyer["categories"]:
            score += 50
        # Quantity fit (0-25 points)
        qty = offer.get("quantity", 0)
        if buyer["min_qty"] <= qty <= buyer["max_qty"]:
            score += 25
        elif qty >= buyer["min_qty"]:
            score += 15
        # Margin fit (0-25 points) — if offer margin meets buyer's target
        if offer.get("margin_pct") and offer["margin_pct"] >= buyer["target_margin_pct"]:
            score += 25
        elif offer.get("margin_pct") and offer["margin_pct"] >= buyer["target_margin_pct"] * 0.8:
            score += 15
        if score > 0:
            results.append({
                "buyer_id": buyer["id"],
                "buyer_name": buyer["name"],
                "rep": buyer["rep"],
                "fit_score": score,
            })
    results.sort(key=lambda x: x["fit_score"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
def _category_pills(categories):
    """Render a list of category strings as colored pill spans."""
    return html.Div(
        [pill(cat, CATEGORY_COLORS.get(cat, COLORS["text_muted"])) for cat in categories],
        style={"display": "flex", "gap": "4px", "flexWrap": "wrap"},
    )


def _score_bar(score):
    """Small colored bar representing a match score 0-100."""
    if score >= 75:
        color = COLORS["success"]
    elif score >= 50:
        color = COLORS["warning"]
    else:
        color = COLORS["danger"]
    return html.Div([
        html.Div(style={
            "width": f"{score}%", "height": "8px",
            "borderRadius": "4px", "background": color,
        }),
    ], style={
        "width": "100%", "height": "8px",
        "borderRadius": "4px", "background": f"{COLORS['card_border']}",
    })


def _build_buyer_table_rows(buyers):
    """Build a styled HTML table body for the buyer directory."""
    rows = []
    for b in buyers:
        rows.append(html.Tr([
            html.Td(b["name"], style={"fontWeight": "600"}),
            html.Td(b["rep"]),
            html.Td(_category_pills(b.get("categories", []))),
            html.Td(f"{b.get('target_margin_pct', 0):.0f}%",
                     style={"textAlign": "center"}),
            html.Td(f"{b.get('min_qty', 0):,}", style={"textAlign": "right"}),
            html.Td(f"{b.get('max_qty', 0):,}", style={"textAlign": "right"}),
            html.Td(b.get("contact_email", ""),
                     style={"fontSize": "0.8rem", "color": COLORS["info"]}),
            html.Td(b.get("created_at", ""),
                     style={"fontSize": "0.8rem", "color": COLORS["text_muted"]}),
        ], style={"borderBottom": f"1px solid {COLORS['card_border']}"}))
    return rows


def _build_match_cards(offers, buyers):
    """Build match suggestion cards for unmatched offers."""
    unmatched = [o for o in offers if not o.get("assigned_buyer_id")]
    if not unmatched:
        return html.Div([
            html.I(className="bi bi-check-circle me-2",
                   style={"color": COLORS["success"]}),
            html.Span("All current offers have been matched to buyers.",
                       style={"color": COLORS["text_muted"], "fontSize": "0.9rem"}),
        ], style={
            "textAlign": "center", "padding": "40px 20px",
        })

    cards = []
    for offer in unmatched[:10]:
        matches = match_buyers(offer, buyers)
        top_matches = matches[:3]

        offer_header = html.Div([
            html.Div([
                html.Span(offer.get("product_name", offer.get("title", "Unknown Offer")),
                          style={"fontWeight": "700", "color": COLORS["text"],
                                 "fontSize": "0.95rem"}),
                pill(offer.get("category", "N/A"),
                     CATEGORY_COLORS.get(offer.get("category", ""), COLORS["text_muted"])),
            ], style={"display": "flex", "gap": "10px", "alignItems": "center",
                       "flexWrap": "wrap"}),
            html.Div([
                html.Span(f"Qty: {offer.get('quantity', 'N/A'):,}" if isinstance(
                    offer.get('quantity'), (int, float)) else "Qty: N/A",
                          style={"color": COLORS["text_muted"], "fontSize": "0.8rem",
                                 "marginRight": "16px"}),
                html.Span(
                    f"Margin: {offer.get('margin_pct', 'N/A')}%"
                    if offer.get("margin_pct") else "Margin: N/A",
                    style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
            ], style={"marginTop": "4px"}),
        ], style={"marginBottom": "12px"})

        if not top_matches:
            match_rows = html.Div([
                html.Span("No matching buyers found.",
                          style={"color": COLORS["text_muted"], "fontSize": "0.85rem"}),
            ])
        else:
            match_items = []
            for m in top_matches:
                match_items.append(html.Div([
                    html.Div([
                        html.Div([
                            html.Span(m["buyer_name"],
                                      style={"fontWeight": "600", "color": COLORS["text"],
                                             "fontSize": "0.85rem"}),
                            html.Span(f" ({m['rep']})",
                                      style={"color": COLORS["text_muted"],
                                             "fontSize": "0.8rem"}),
                        ]),
                        html.Div([
                            _score_bar(m["fit_score"]),
                            html.Span(f"{m['fit_score']}pts",
                                      style={"color": COLORS["text_muted"],
                                             "fontSize": "0.75rem", "marginLeft": "8px",
                                             "whiteSpace": "nowrap"}),
                        ], style={"display": "flex", "alignItems": "center",
                                  "gap": "4px", "marginTop": "4px", "maxWidth": "200px"}),
                    ], style={"flex": "1"}),
                    html.Button([
                        html.I(className="bi bi-link-45deg me-1"),
                        "Assign",
                    ], id={"type": "buyers-assign-btn",
                           "offer_idx": str(offer.get("id", offers.index(offer))),
                           "buyer_id": str(m["buyer_id"])},
                       className="btn-outline-dark",
                       style={"fontSize": "0.75rem", "padding": "4px 10px"}),
                ], style={
                    "display": "flex", "justifyContent": "space-between",
                    "alignItems": "center", "padding": "8px 0",
                    "borderBottom": f"1px solid {COLORS['card_border']}",
                }))
            match_rows = html.Div(match_items)

        cards.append(html.Div([
            offer_header,
            match_rows,
        ], style={
            "background": COLORS["card"],
            "border": f"1px solid {COLORS['card_border']}",
            "borderRadius": "10px",
            "padding": "16px 20px",
        }))

    return html.Div(cards, style={"display": "flex", "flexDirection": "column",
                                   "gap": "12px"})


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
def layout():
    buyers = _load_buyers()
    offers = _load_offers()

    # KPI calculations
    total_buyers = len(buyers)
    active_reps = len(set(b["rep"] for b in buyers)) if buyers else 0
    all_cats = set()
    for b in buyers:
        all_cats.update(b.get("categories", []))
    categories_covered = len(all_cats)
    avg_margin = (
        round(sum(b.get("target_margin_pct", 0) for b in buyers) / total_buyers, 1)
        if total_buyers else 0
    )

    # Buyer directory table (styled HTML)
    _cell = {
        "padding": "12px 16px",
        "fontSize": "0.85rem",
        "color": COLORS["text"],
        "borderBottom": f"1px solid {COLORS['card_border']}",
        "verticalAlign": "middle",
    }
    _header = {
        **_cell,
        "fontWeight": "700",
        "color": COLORS["text_muted"],
        "fontSize": "0.75rem",
        "textTransform": "uppercase",
        "letterSpacing": "0.05em",
        "background": COLORS["sidebar"],
        "position": "sticky",
        "top": "0",
    }

    buyer_table = html.Div([
        html.Table([
            html.Thead(html.Tr([
                html.Th("Name", style=_header),
                html.Th("Rep", style=_header),
                html.Th("Categories", style=_header),
                html.Th("Target Margin", style={**_header, "textAlign": "center"}),
                html.Th("Min Qty", style={**_header, "textAlign": "right"}),
                html.Th("Max Qty", style={**_header, "textAlign": "right"}),
                html.Th("Contact", style=_header),
                html.Th("Created", style=_header),
            ])),
            html.Tbody(
                _build_buyer_table_rows(buyers),
                id="buyers-table-body",
            ),
        ], style={
            "width": "100%",
            "borderCollapse": "collapse",
        }),
    ], style={"overflowX": "auto"})

    return html.Div([
        # Stores
        dcc.Store(id="buyers-refresh-trigger", data=0),

        # Page header
        html.Div([
            html.H2("Buyers"),
            html.P("Manage buyer profiles, target preferences, and match incoming offers to the best-fit buyers"),
        ], className="page-header"),

        # KPI row
        html.Div([
            kpi_card("Total Buyers", str(total_buyers), "bi-people-fill",
                     COLORS["primary"]),
            kpi_card("Active Reps", str(active_reps), "bi-person-badge",
                     COLORS["success"]),
            kpi_card("Categories Covered", str(categories_covered), "bi-tags",
                     COLORS["info"]),
            kpi_card("Avg Target Margin", f"{avg_margin}%", "bi-percent",
                     COLORS["warning"]),
        ], style={
            "display": "grid",
            "gridTemplateColumns": "repeat(auto-fit, minmax(200px, 1fr))",
            "gap": "12px", "marginBottom": "20px",
        }),

        # Buyer directory
        html.Div([
            html.Div([
                html.I(className="bi bi-people me-2",
                       style={"color": COLORS["primary"], "fontSize": "1.2rem"}),
                html.H6("Buyer Directory", className="mb-0",
                         style={"color": COLORS["text"], "fontWeight": "600"}),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "16px"}),
            buyer_table,
        ], className="dash-card", style={"marginBottom": "20px"}),

        # Add Buyer form
        html.Div([
            html.Div([
                html.I(className="bi bi-person-plus me-2",
                       style={"color": COLORS["success"], "fontSize": "1.2rem"}),
                html.H6("Add Buyer", className="mb-0",
                         style={"color": COLORS["text"], "fontWeight": "600"}),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "16px"}),

            # Row 1: Name + Rep
            html.Div([
                form_group("Buyer Name",
                           styled_input("buyers-name", "Company or buyer name",
                                        type="text")),
                form_group("Rep Name",
                           styled_input("buyers-rep", "Sales rep name",
                                        type="text")),
            ], className="grid-row grid-2"),

            # Row 2: Categories + Target Margin
            html.Div([
                form_group("Categories",
                           styled_dropdown("buyers-categories",
                                           [{"label": c, "value": c}
                                            for c in ALL_CATEGORIES],
                                           placeholder="Select categories...",
                                           multi=True)),
                form_group("Target Margin %",
                           styled_input("buyers-margin", "25", type="number",
                                        min=0, max=100, step=0.5)),
            ], className="grid-row grid-2"),

            # Row 3: Min Qty + Max Qty
            html.Div([
                form_group("Min Qty",
                           styled_input("buyers-min-qty", "100", type="number",
                                        min=0)),
                form_group("Max Qty",
                           styled_input("buyers-max-qty", "5000", type="number",
                                        min=0)),
            ], className="grid-row grid-2"),

            # Row 4: Contact Email + Phone
            html.Div([
                form_group("Contact Email",
                           styled_input("buyers-email", "buyer@company.com",
                                        type="email")),
                form_group("Phone",
                           styled_input("buyers-phone", "(555) 000-0000",
                                        type="tel")),
            ], className="grid-row grid-2"),

            # Row 5: Notes
            form_group("Notes",
                       styled_input("buyers-notes",
                                    "Payment terms, preferences, special instructions...",
                                    type="text")),

            # Save button + status
            html.Div([
                html.Button([
                    html.I(className="bi bi-plus-circle me-2"),
                    "Add Buyer",
                ], id="buyers-add-btn", className="btn-primary-dark"),
                html.Div(id="buyers-add-status", style={"marginTop": "12px"}),
            ]),
        ], className="dash-card", style={"marginBottom": "20px"}),

        # Matching Suggestions
        html.Div([
            html.Div([
                html.Div([
                    html.I(className="bi bi-diagram-3 me-2",
                           style={"color": COLORS["purple"], "fontSize": "1.2rem"}),
                    html.H6("Matching Suggestions", className="mb-0",
                             style={"color": COLORS["text"], "fontWeight": "600"}),
                ], style={"display": "flex", "alignItems": "center"}),
                html.Button([
                    html.I(className="bi bi-arrow-repeat me-2"),
                    "Refresh Matches",
                ], id="buyers-refresh-btn", className="btn-outline-dark",
                   style={"fontSize": "0.8rem", "padding": "6px 14px"}),
            ], style={
                "display": "flex", "justifyContent": "space-between",
                "alignItems": "center", "marginBottom": "16px",
            }),
            html.P("Unmatched incoming offers paired with best-fit buyers based on "
                   "category, quantity range, and target margin.",
                   style={"color": COLORS["text_muted"], "fontSize": "0.8rem",
                          "marginBottom": "16px"}),
            html.Div(
                _build_match_cards(offers, buyers),
                id="buyers-match-results",
            ),
            html.Div(id="buyers-assign-status", style={"marginTop": "12px"}),
        ], className="dash-card", style={"marginBottom": "20px"}),
    ])


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

# -- Add buyer ---------------------------------------------------------------
@callback(
    Output("buyers-add-status", "children"),
    Output("buyers-table-body", "children"),
    Output("buyers-name", "value"),
    Output("buyers-rep", "value"),
    Output("buyers-categories", "value"),
    Output("buyers-margin", "value"),
    Output("buyers-min-qty", "value"),
    Output("buyers-max-qty", "value"),
    Output("buyers-email", "value"),
    Output("buyers-phone", "value"),
    Output("buyers-notes", "value"),
    Input("buyers-add-btn", "n_clicks"),
    State("buyers-name", "value"),
    State("buyers-rep", "value"),
    State("buyers-categories", "value"),
    State("buyers-margin", "value"),
    State("buyers-min-qty", "value"),
    State("buyers-max-qty", "value"),
    State("buyers-email", "value"),
    State("buyers-phone", "value"),
    State("buyers-notes", "value"),
    prevent_initial_call=True,
)
def add_buyer(n_clicks, name, rep, categories, margin, min_qty, max_qty,
              email, phone, notes):
    if not n_clicks:
        return (no_update,) * 11

    # Validation
    if not name or not name.strip():
        return (
            html.Div([
                html.I(className="bi bi-exclamation-triangle me-2",
                       style={"color": COLORS["danger"]}),
                html.Span("Buyer name is required.",
                          style={"color": COLORS["danger"], "fontSize": "0.85rem"}),
            ]),
            no_update, no_update, no_update, no_update, no_update,
            no_update, no_update, no_update, no_update, no_update,
        )

    buyers = _load_buyers()
    next_id = max((b["id"] for b in buyers), default=0) + 1

    new_buyer = {
        "id": next_id,
        "name": name.strip(),
        "rep": (rep or "").strip(),
        "categories": categories or [],
        "target_margin_pct": float(margin or 25),
        "min_qty": int(min_qty or 0),
        "max_qty": int(max_qty or 0),
        "contact_email": (email or "").strip(),
        "phone": (phone or "").strip(),
        "notes": (notes or "").strip(),
        "created_at": datetime.now().strftime("%Y-%m-%d"),
    }
    buyers.append(new_buyer)
    _save_buyers(buyers)

    status = html.Div([
        html.I(className="bi bi-check-circle-fill me-2",
               style={"color": COLORS["success"]}),
        html.Span(f"Added buyer \"{new_buyer['name']}\" successfully.",
                  style={"color": COLORS["success"], "fontWeight": "500",
                         "fontSize": "0.85rem"}),
    ])

    return (
        status,
        _build_buyer_table_rows(buyers),
        "",   # clear name
        "",   # clear rep
        [],   # clear categories
        None, # clear margin
        None, # clear min_qty
        None, # clear max_qty
        "",   # clear email
        "",   # clear phone
        "",   # clear notes
    )


# -- Refresh matches --------------------------------------------------------
@callback(
    Output("buyers-match-results", "children"),
    Input("buyers-refresh-btn", "n_clicks"),
    prevent_initial_call=True,
)
def refresh_matches(n_clicks):
    if not n_clicks:
        return no_update
    buyers = _load_buyers()
    offers = _load_offers()
    return _build_match_cards(offers, buyers)


# -- Assign buyer to offer (pattern-matching callback) -----------------------
from dash import ALL, ctx

@callback(
    Output("buyers-assign-status", "children"),
    Output("buyers-match-results", "children", allow_duplicate=True),
    Input({"type": "buyers-assign-btn", "offer_idx": ALL, "buyer_id": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def assign_buyer(n_clicks_list):
    # Determine which button was clicked
    if not any(n_clicks_list):
        return no_update, no_update

    triggered = ctx.triggered_id
    if not triggered:
        return no_update, no_update

    offer_idx = triggered["offer_idx"]
    buyer_id = int(triggered["buyer_id"])

    offers = _load_offers()
    buyers = _load_buyers()

    # Find the offer by id or index
    target_offer = None
    for o in offers:
        if str(o.get("id", "")) == str(offer_idx):
            target_offer = o
            break
    if target_offer is None:
        # Fallback: try as list index
        try:
            idx = int(offer_idx)
            if 0 <= idx < len(offers):
                target_offer = offers[idx]
        except (ValueError, IndexError):
            pass

    if target_offer is None:
        return (
            html.Div([
                html.I(className="bi bi-exclamation-triangle me-2",
                       style={"color": COLORS["danger"]}),
                html.Span("Offer not found.",
                          style={"color": COLORS["danger"], "fontSize": "0.85rem"}),
            ]),
            no_update,
        )

    # Find buyer name for status message
    buyer_name = "Unknown"
    for b in buyers:
        if b["id"] == buyer_id:
            buyer_name = b["name"]
            break

    target_offer["assigned_buyer_id"] = buyer_id
    target_offer["assigned_buyer_name"] = buyer_name
    target_offer["assigned_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    _save_offers(offers)

    status = html.Div([
        html.I(className="bi bi-check-circle-fill me-2",
               style={"color": COLORS["success"]}),
        html.Span(
            f"Assigned \"{target_offer.get('product_name', target_offer.get('title', 'offer'))}\" "
            f"to {buyer_name}.",
            style={"color": COLORS["success"], "fontWeight": "500",
                   "fontSize": "0.85rem"}),
    ])

    return status, _build_match_cards(offers, buyers)
