import json
import os
from datetime import datetime

from dash import html, dcc, callback, Input, Output, State, no_update, dash_table

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
    """Render a list of category strings as tiny colored pill spans."""
    return html.Div(
        [html.Span(cat[:3], title=cat, style={
            "background": f"{CATEGORY_COLORS.get(cat, COLORS['text_muted'])}25",
            "color": CATEGORY_COLORS.get(cat, COLORS["text_muted"]),
            "padding": "1px 5px", "borderRadius": "8px", "fontSize": "0.65rem",
            "fontWeight": "600", "lineHeight": "1.2", "cursor": "default",
        }) for cat in categories],
        style={"display": "flex", "gap": "3px", "flexWrap": "wrap", "maxWidth": "120px"},
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


def _build_buyer_table_data(buyers):
    """Build DataTable data for the buyer directory."""
    rows = []
    for b in buyers:
        addr = b.get("shipping_address", {})
        loc = ""
        if addr.get("city") and addr.get("state"):
            loc = f"{addr['city']}, {addr['state']}"
        rows.append({
            "id": b.get("id"),
            "name": b.get("name", ""),
            "rep": b.get("rep", ""),
            "categories": ", ".join(b.get("categories", [])),
            "margin": b.get("target_margin_pct", 0),
            "email": b.get("contact_email", ""),
            "phone": b.get("phone", ""),
            "location": loc,
        })
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

    buyer_table_data = []
    for b in buyers:
        addr = b.get("shipping_address", {})
        loc = ""
        if addr.get("city") and addr.get("state"):
            loc = f"{addr['city']}, {addr['state']}"
        buyer_table_data.append({
            "id": b.get("id"),
            "name": b.get("name", ""),
            "rep": b.get("rep", ""),
            "categories": ", ".join(b.get("categories", [])),
            "margin": b.get("target_margin_pct", 0),
            "email": b.get("contact_email", ""),
            "phone": b.get("phone", ""),
            "location": loc,
        })

    buyer_table = html.Div([
        dash_table.DataTable(
            id="buyers-directory-table",
            columns=[
                {"name": "Name", "id": "name"},
                {"name": "Rep", "id": "rep"},
                {"name": "Categories", "id": "categories"},
                {"name": "Margin", "id": "margin", "type": "numeric"},
                {"name": "Email", "id": "email"},
                {"name": "Phone", "id": "phone"},
                {"name": "Location", "id": "location"},
            ],
            data=buyer_table_data,
            sort_action="native",
            sort_mode="multi",
            style_header={
                "backgroundColor": COLORS["sidebar"],
                "color": COLORS["text_muted"],
                "fontWeight": "700",
                "fontSize": "0.75rem",
                "textTransform": "uppercase",
                "letterSpacing": "0.05em",
                "border": f"1px solid {COLORS['card_border']}",
                "padding": "10px 14px",
            },
            style_cell={
                "backgroundColor": COLORS["card"],
                "color": COLORS["text"],
                "border": f"1px solid {COLORS['card_border']}",
                "fontSize": "0.82rem",
                "padding": "8px 14px",
                "textAlign": "left",
                "maxWidth": "180px",
                "overflow": "hidden",
                "textOverflow": "ellipsis",
                "whiteSpace": "nowrap",
            },
            style_data_conditional=[
                {"if": {"state": "active"}, "backgroundColor": COLORS["hover"]},
                {"if": {"state": "selected"}, "backgroundColor": COLORS["hover"]},
            ],
            page_size=20,
        ),
    ])

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

        # Add / Edit Buyer form
        html.Div([
            html.Div([
                html.Div([
                    html.I(className="bi bi-person-plus me-2",
                           style={"color": COLORS["success"], "fontSize": "1.2rem"}),
                    html.H6("Add / Edit Buyer", className="mb-0",
                             style={"color": COLORS["text"], "fontWeight": "600"}),
                ], style={"display": "flex", "alignItems": "center"}),
                html.Div([
                    styled_dropdown("buyers-edit-select",
                                    [{"label": f"{b['name']} ({b.get('rep','')})", "value": b["id"]}
                                     for b in buyers],
                                    placeholder="Select buyer to edit...",
                                    clearable=True),
                ], style={"minWidth": "250px"}),
            ], style={"display": "flex", "justifyContent": "space-between",
                       "alignItems": "center", "marginBottom": "16px", "gap": "16px"}),
            dcc.Store(id="buyers-editing-id", data=None),

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

            # Hidden inputs to keep callbacks working
            dcc.Input(id="buyers-min-qty", type="hidden", value=0),
            dcc.Input(id="buyers-max-qty", type="hidden", value=0),

            # Row 3: Contact Email + Phone
            html.Div([
                form_group("Contact Email",
                           styled_input("buyers-email", "buyer@company.com",
                                        type="email")),
                form_group("Phone",
                           styled_input("buyers-phone", "(555) 000-0000",
                                        type="tel")),
            ], className="grid-row grid-2"),

            # Row 5: Notes + Payment Terms
            html.Div([
                form_group("Payment Terms",
                           styled_dropdown("buyers-payment-terms",
                                           [{"label": t, "value": t} for t in
                                            ["Wire before ship", "Net 15", "Net 30",
                                             "COD", "50% deposit", "Zelle before ship"]],
                                           placeholder="Select terms...",
                                           value="Wire before ship")),
                form_group("Notes",
                           styled_input("buyers-notes",
                                        "Preferences, special instructions...",
                                        type="text")),
            ], className="grid-row grid-2"),

            # Shipping Address section
            html.Div([
                html.Div([
                    html.I(className="bi bi-geo-alt me-2",
                           style={"color": COLORS["info"], "fontSize": "1rem"}),
                    html.Span("Shipping Address", style={"fontWeight": "600",
                              "color": COLORS["text"], "fontSize": "0.9rem"}),
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "12px"}),

                html.Div([
                    form_group("Recipient Name",
                               styled_input("buyers-addr-name", "Full name",
                                            type="text")),
                    form_group("Company",
                               styled_input("buyers-addr-company", "Company (optional)",
                                            type="text")),
                ], className="grid-row grid-2"),
                html.Div([
                    form_group("Address Line 1",
                               styled_input("buyers-addr-line1", "Street address",
                                            type="text")),
                    form_group("Address Line 2",
                               styled_input("buyers-addr-line2", "Suite, unit (optional)",
                                            type="text")),
                ], className="grid-row grid-2"),
                html.Div([
                    form_group("City",
                               styled_input("buyers-addr-city", "City",
                                            type="text")),
                    form_group("State",
                               styled_input("buyers-addr-state", "CA",
                                            type="text")),
                    form_group("ZIP Code",
                               styled_input("buyers-addr-zip", "90210",
                                            type="text")),
                ], className="grid-row grid-3"),
                html.Div(id="buyers-addr-validation", style={"marginTop": "8px"}),
                html.Button([
                    html.I(className="bi bi-check2-circle me-2"),
                    "Validate Address",
                ], id="buyers-validate-addr-btn", className="btn-outline-dark",
                   style={"fontSize": "0.8rem", "padding": "6px 14px", "marginTop": "4px"}),
            ], style={
                "background": f"{COLORS['info']}08",
                "border": f"1px solid {COLORS['card_border']}",
                "borderRadius": "8px", "padding": "16px", "marginBottom": "16px",
            }),

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
    Output("buyers-directory-table", "data"),
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
    State("buyers-payment-terms", "value"),
    State("buyers-addr-name", "value"),
    State("buyers-addr-company", "value"),
    State("buyers-addr-line1", "value"),
    State("buyers-addr-line2", "value"),
    State("buyers-addr-city", "value"),
    State("buyers-addr-state", "value"),
    State("buyers-addr-zip", "value"),
    State("buyers-editing-id", "data"),
    prevent_initial_call=True,
)
def add_or_update_buyer(n_clicks, name, rep, categories, margin, min_qty, max_qty,
                        email, phone, notes, payment_terms,
                        addr_name, addr_company, addr_line1, addr_line2,
                        addr_city, addr_state, addr_zip, editing_id):
    if not n_clicks:
        return (no_update,) * 11

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

    buyer_data = {
        "name": name.strip(),
        "rep": (rep or "").strip(),
        "categories": categories or [],
        "target_margin_pct": float(margin or 25),
        "min_qty": int(min_qty or 0),
        "max_qty": int(max_qty or 0),
        "contact_email": (email or "").strip(),
        "phone": (phone or "").strip(),
        "notes": (notes or "").strip(),
        "payment_terms": payment_terms or "Wire before ship",
        "shipping_address": {
            "name": (addr_name or name).strip(),
            "company": (addr_company or "").strip(),
            "line1": (addr_line1 or "").strip(),
            "line2": (addr_line2 or "").strip(),
            "city": (addr_city or "").strip(),
            "state": (addr_state or "").strip(),
            "zip": (addr_zip or "").strip(),
            "phone": (phone or "").strip(),
        },
    }

    if editing_id:
        # Update existing buyer
        for b in buyers:
            if b.get("id") == editing_id:
                b.update(buyer_data)
                break
        action = "Updated"
    else:
        # Add new buyer
        next_id = max((b["id"] for b in buyers), default=0) + 1
        buyer_data["id"] = next_id
        buyer_data["created_at"] = datetime.now().strftime("%Y-%m-%d")
        buyers.append(buyer_data)
        action = "Added"

    _save_buyers(buyers)

    status = html.Div([
        html.I(className="bi bi-check-circle-fill me-2",
               style={"color": COLORS["success"]}),
        html.Span(f"{action} buyer \"{buyer_data['name']}\" successfully.",
                  style={"color": COLORS["success"], "fontWeight": "500",
                         "fontSize": "0.85rem"}),
    ])

    return (
        status,
        _build_buyer_table_data(buyers),
        "", "", [], None, None, None, "", "", "",
    )


# -- Load buyer for editing ---------------------------------------------------
@callback(
    Output("buyers-name", "value", allow_duplicate=True),
    Output("buyers-rep", "value", allow_duplicate=True),
    Output("buyers-categories", "value", allow_duplicate=True),
    Output("buyers-margin", "value", allow_duplicate=True),
    Output("buyers-min-qty", "value", allow_duplicate=True),
    Output("buyers-max-qty", "value", allow_duplicate=True),
    Output("buyers-email", "value", allow_duplicate=True),
    Output("buyers-phone", "value", allow_duplicate=True),
    Output("buyers-notes", "value", allow_duplicate=True),
    Output("buyers-payment-terms", "value"),
    Output("buyers-addr-name", "value"),
    Output("buyers-addr-company", "value"),
    Output("buyers-addr-line1", "value"),
    Output("buyers-addr-line2", "value"),
    Output("buyers-addr-city", "value"),
    Output("buyers-addr-state", "value"),
    Output("buyers-addr-zip", "value"),
    Output("buyers-editing-id", "data"),
    Output("buyers-add-btn", "children"),
    Input("buyers-edit-select", "value"),
    prevent_initial_call=True,
)
def load_buyer_for_edit(buyer_id):
    add_label = [html.I(className="bi bi-plus-circle me-2"), "Add Buyer"]
    save_label = [html.I(className="bi bi-check-lg me-2"), "Save Changes"]

    if not buyer_id:
        return "", "", [], None, None, None, "", "", "", "Wire before ship", "", "", "", "", "", "", "", None, add_label

    buyers = _load_buyers()
    b = next((x for x in buyers if x.get("id") == buyer_id), None)
    if not b:
        return (no_update,) * 19

    addr = b.get("shipping_address", {})

    return (
        b.get("name", ""),
        b.get("rep", ""),
        b.get("categories", []),
        b.get("target_margin_pct", 25),
        b.get("min_qty", 0),
        b.get("max_qty", 0),
        b.get("contact_email", ""),
        b.get("phone", ""),
        b.get("notes", ""),
        b.get("payment_terms", "Wire before ship"),
        addr.get("name", "") or b.get("name", ""),
        addr.get("company", "") or b.get("name", ""),
        addr.get("line1", ""),
        addr.get("line2", ""),
        addr.get("city", ""),
        addr.get("state", ""),
        addr.get("zip", ""),
        buyer_id,
        save_label,
    )


# -- Address validation --------------------------------------------------------
@callback(
    Output("buyers-addr-validation", "children"),
    Input("buyers-validate-addr-btn", "n_clicks"),
    State("buyers-addr-line1", "value"),
    State("buyers-addr-city", "value"),
    State("buyers-addr-state", "value"),
    State("buyers-addr-zip", "value"),
    prevent_initial_call=True,
)
def validate_address(n_clicks, line1, city, state, zip_code):
    """Validate address using OpenStreetMap Nominatim geocoding."""
    if not n_clicks:
        return no_update

    if not line1 or not city or not state:
        return html.Div([
            html.I(className="bi bi-exclamation-triangle me-2",
                   style={"color": COLORS["warning"]}),
            html.Span("Please enter at least street, city, and state.",
                      style={"color": COLORS["warning"], "fontSize": "0.85rem"}),
        ])

    import requests as _req
    query = f"{line1}, {city}, {state} {zip_code or ''}, USA"
    try:
        resp = _req.get("https://nominatim.openstreetmap.org/search", params={
            "q": query,
            "format": "json",
            "countrycodes": "us",
            "limit": 1,
            "addressdetails": 1,
        }, headers={"User-Agent": "KeithEnterprises/1.0"}, timeout=10)

        results = resp.json()
        if results:
            display = results[0].get("display_name", "")
            return html.Div([
                html.Div([
                    html.I(className="bi bi-patch-check-fill me-2",
                           style={"color": COLORS["success"], "fontSize": "1.2rem"}),
                    html.Span("ADDRESS VALIDATED",
                              style={"color": COLORS["success"], "fontWeight": "700",
                                     "fontSize": "0.9rem", "letterSpacing": "0.05em"}),
                ], style={"display": "flex", "alignItems": "center", "marginBottom": "4px"}),
                html.Span(display[:150],
                          style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
            ], style={
                "background": f"{COLORS['success']}15",
                "border": f"1px solid {COLORS['success']}40",
                "borderRadius": "6px", "padding": "10px 14px",
            })
        else:
            return html.Div([
                html.I(className="bi bi-x-circle me-2",
                       style={"color": COLORS["danger"]}),
                html.Span("Address not found. Please check and try again.",
                          style={"color": COLORS["danger"], "fontSize": "0.85rem"}),
            ])
    except Exception as e:
        return html.Div([
            html.I(className="bi bi-exclamation-triangle me-2",
                   style={"color": COLORS["warning"]}),
            html.Span(f"Validation unavailable: {e}",
                      style={"color": COLORS["warning"], "fontSize": "0.85rem"}),
        ])


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
