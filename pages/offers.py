import json
import os
from datetime import datetime, date

from dash import html, dcc, callback, Input, Output, State, dash_table, no_update, ctx, ALL
from config import COLORS
from components.cards import kpi_card
from components.forms import styled_input, styled_dropdown, form_group

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "offers.json")
BUYERS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "buyers.json")

CATEGORIES = ["OTC", "HBA", "Toys", "Tools", "Electronics", "Grocery", "Household", "Apparel", "Other"]
SOURCES = ["WhatsApp", "Email", "Phone", "Walk-in", "Other"]
STATUSES = ["new", "evaluating", "matched", "accepted", "rejected"]

STATUS_COLORS = {
    "new": COLORS["info"],
    "evaluating": COLORS["warning"],
    "matched": COLORS["purple"],
    "accepted": COLORS["success"],
    "rejected": COLORS["danger"],
}

STATUS_LABELS = {
    "new": "New",
    "evaluating": "Evaluating",
    "matched": "Matched",
    "accepted": "Accepted",
    "rejected": "Rejected",
}

CATEGORY_COLORS = {
    "OTC": "#58a6ff",
    "HBA": "#bc8cff",
    "Toys": "#f0883e",
    "Tools": "#8b949e",
    "Electronics": "#79c0ff",
    "Grocery": "#3fb950",
    "Household": "#d29922",
    "Apparel": "#f778ba",
    "Other": "#8b949e",
}


# ── Data helpers ──────────────────────────────────────────────────────────────

def _load_offers():
    """Load offers from JSON file, returning empty list on any error."""
    try:
        if not os.path.exists(DATA_PATH):
            return []
        with open(DATA_PATH) as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return data
    except (json.JSONDecodeError, IOError, OSError):
        return []


def _save_offers(offers):
    """Persist the offers list to JSON."""
    try:
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        with open(DATA_PATH, "w") as f:
            json.dump(offers, f, indent=2)
    except (IOError, OSError) as e:
        raise RuntimeError(f"Failed to save offers: {e}")


def _load_buyers():
    try:
        with open(BUYERS_PATH) as f:
            return json.load(f)
    except Exception:
        return []


def _next_id(offers):
    """Return next available offer ID."""
    if not offers:
        return 1
    return max(o.get("id", 0) for o in offers) + 1


def _format_currency(val):
    """Format a number as currency string."""
    if val is None:
        return "-"
    try:
        return f"${float(val):,.2f}"
    except (ValueError, TypeError):
        return "-"


def _format_pct(val):
    """Format a number as percentage string."""
    if val is None:
        return "-"
    try:
        return f"{float(val):.1f}%"
    except (ValueError, TypeError):
        return "-"


def _format_date(val):
    """Format a datetime string to short date."""
    if not val:
        return "-"
    try:
        dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
        return dt.strftime("%m/%d/%y")
    except (ValueError, TypeError):
        return val[:10] if len(val) >= 10 else val


# ── Layout builders ───────────────────────────────────────────────────────────

def _status_pill_style(status):
    """Return inline style dict for a status pill."""
    color = STATUS_COLORS.get(status, COLORS["text_muted"])
    return {
        "backgroundColor": f"{color}20",
        "color": color,
        "padding": "3px 10px",
        "borderRadius": "20px",
        "fontSize": "0.75rem",
        "fontWeight": "600",
        "display": "inline-block",
        "textTransform": "capitalize",
    }


def _build_filter_button(label, status_value, is_active=False):
    """Build a single filter button."""
    if is_active:
        bg = COLORS["active"]
        color = "#ffffff"
        border = COLORS["active"]
    else:
        bg = "transparent"
        color = COLORS["text_muted"]
        border = COLORS["card_border"]
    return html.Button(
        label,
        id=f"offers-filter-{status_value}",
        n_clicks=0,
        style={
            "background": bg,
            "color": color,
            "border": f"1px solid {border}",
            "borderRadius": "6px",
            "padding": "6px 16px",
            "fontSize": "0.8rem",
            "fontWeight": "500",
            "cursor": "pointer",
            "transition": "all 0.15s ease",
        },
    )


def _build_kpi_row(offers):
    """Build the KPI cards row from current offers data."""
    total = len(offers)
    pending = sum(1 for o in offers if o.get("status") in ("new", "evaluating"))
    matched = sum(1 for o in offers if o.get("status") == "matched")

    today_str = date.today().isoformat()
    today_value = sum(
        o.get("offered_price", 0) * o.get("quantity", 0)
        for o in offers
        if o.get("created_at", "").startswith(today_str)
    )

    return html.Div([
        kpi_card("Total Offers", str(total), "bi-inbox-fill", COLORS["primary"]),
        kpi_card("Pending Review", str(pending), "bi-hourglass-split", COLORS["warning"]),
        kpi_card("Matched", str(matched), "bi-link-45deg", COLORS["purple"]),
        kpi_card("Today's Value", _format_currency(today_value), "bi-currency-dollar",
                 COLORS["success"]),
    ], style={
        "display": "grid",
        "gridTemplateColumns": "repeat(auto-fit, minmax(220px, 1fr))",
        "gap": "16px",
        "marginBottom": "24px",
    })


def _build_table_data(offers, status_filter="all", category_filter=None):
    """Build flat table records from offers, applying filters."""
    filtered = offers
    if status_filter and status_filter != "all":
        filtered = [o for o in filtered if o.get("status") == status_filter]
    if category_filter:
        filtered = [o for o in filtered if o.get("category") == category_filter]

    rows = []
    for o in filtered:
        mp = o.get("marketplace_data") or {}
        sa = o.get("sa_data") or {}
        buyers = o.get("matched_buyers") or []
        buyer_name = buyers[0]["buyer_name"] if buyers else "-"

        # Use SA data if available, fall back to scraped data
        buy_box = sa.get("buy_box_price") or mp.get("amazon_price") or 0
        buyer_profit = sa.get("buyer_profit") or 0
        monthly_sales = sa.get("estimated_monthly_sales") or 0
        fba_sellers = sa.get("fba_sellers", "")
        wholesale = o.get("wholesale_price") or 0
        our_margin = o.get("our_margin_pct") or sa.get("our_margin_pct") or 0

        rows.append({
            "id": o.get("id"),
            "status": STATUS_LABELS.get(o.get("status", ""), o.get("status", "")),
            "product_name": o.get("product_name", ""),
            "category": o.get("category", ""),
            "supplier_cost": round(float(o.get("per_unit_cost") or 0), 2),
            "wholesale": round(float(wholesale), 2),
            "our_margin": round(float(our_margin), 1),
            "buy_box": round(float(buy_box), 2),
            "buyer_profit": round(float(buyer_profit), 2),
            "monthly_sales": monthly_sales,
            "fba_sellers": fba_sellers if fba_sellers != "" else "",
            "quantity": o.get("quantity") or 0,
            "matched_buyer": buyer_name,
            "expiry": _format_date(o.get("expiry", "")),
        })
    return rows


TABLE_COLUMNS = [
    {"name": "Status", "id": "status"},
    {"name": "Product", "id": "product_name"},
    {"name": "Category", "id": "category"},
    {"name": "Our Cost", "id": "supplier_cost", "type": "numeric"},
    {"name": "Our Price", "id": "wholesale", "type": "numeric"},
    {"name": "Our Margin %", "id": "our_margin", "type": "numeric"},
    {"name": "Buy Box", "id": "buy_box", "type": "numeric"},
    {"name": "Buyer Profit", "id": "buyer_profit", "type": "numeric"},
    {"name": "Mo. Sales", "id": "monthly_sales", "type": "numeric"},
    {"name": "FBA", "id": "fba_sellers"},
    {"name": "Avail", "id": "quantity", "type": "numeric"},
    {"name": "Buyer", "id": "matched_buyer"},
    {"name": "Expiry", "id": "expiry"},
]


def _status_conditional_styles():
    """Return conditional style rules for status column color-coding."""
    rules = []
    for status_key, color in STATUS_COLORS.items():
        label = STATUS_LABELS[status_key]
        rules.append({
            "if": {
                "filter_query": f'{{status}} = "{label}"',
                "column_id": "status",
            },
            "backgroundColor": f"{color}18",
            "color": color,
            "fontWeight": "600",
        })
    return rules


# ── Main layout ───────────────────────────────────────────────────────────────

def layout():
    offers = _load_offers()
    table_data = _build_table_data(offers)
    no_price = sum(1 for o in offers if not (o.get("marketplace_data") or {}).get("amazon_price"))
    no_sa = sum(1 for o in offers if o.get("upc") and not o.get("sa_data", {}).get("buy_box_price"))

    return html.Div([
        # Hidden stores
        dcc.Store(id="offers-active-filter", data="all"),
        dcc.Store(id="offers-selected-id", data=None),

        # Page header
        html.Div([
            html.H2("Offer Log"),
            html.P("Track, evaluate, and match wholesale inventory offers from all channels"),
        ], className="page-header"),

        # KPI row
        html.Div(id="offers-kpi-row", children=_build_kpi_row(offers)),

        # Filter bar
        html.Div([
            html.Div([
                _build_filter_button("All", "all", is_active=True),
                _build_filter_button("New", "new"),
                _build_filter_button("Evaluating", "evaluating"),
                _build_filter_button("Matched", "matched"),
                _build_filter_button("Accepted", "accepted"),
                _build_filter_button("Rejected", "rejected"),
            ], style={
                "display": "flex", "gap": "8px", "flexWrap": "wrap",
                "alignItems": "center",
            }),
            html.Div([
                styled_dropdown(
                    "offers-category-filter",
                    [{"label": c, "value": c} for c in CATEGORIES],
                    value=None,
                    placeholder="All Categories",
                    clearable=True,
                ),
            ], style={"minWidth": "180px"}),
        ], style={
            "display": "flex", "justifyContent": "space-between",
            "alignItems": "center", "gap": "16px", "flexWrap": "wrap",
            "marginBottom": "20px", "padding": "16px",
            "background": COLORS["card"], "borderRadius": "8px",
            "border": f"1px solid {COLORS['card_border']}",
        }),

        # Seller Assistant enrichment banner
        html.Div([
            html.Div([
                html.Div([
                    html.I(className="bi bi-lightning-charge-fill",
                           style={"fontSize": "1.3rem", "color": COLORS["purple"]}),
                ], style={"flexShrink": "0"}),
                html.Div([
                    html.Span("Seller Assistant Enrichment ",
                              style={"color": COLORS["text"], "fontWeight": "600"}),
                    html.Span(id="offers-sa-pending-text",
                              children=f"— {no_sa} offers need enrichment (Buy Box, fees, restrictions, sales data)",
                              style={"color": COLORS["text_muted"]}),
                ], style={"fontSize": "0.85rem", "flex": "1"}),
                html.Div([
                    styled_dropdown(
                        "offers-sa-batch-size",
                        [{"label": f"{n} offers", "value": n} for n in [10, 25, 50]],
                        value=25,
                        placeholder="Batch",
                        clearable=False,
                    ),
                ], style={"minWidth": "120px"}),
                html.Div([
                    html.Button([
                        html.I(className="bi bi-lightning-charge me-2"),
                        "Enrich Products",
                    ], id="offers-sa-enrich-btn", className="btn-primary-dark",
                        style={"fontSize": "0.8rem", "padding": "8px 16px", "whiteSpace": "nowrap"}),
                ]),
            ], style={"display": "flex", "alignItems": "center", "gap": "16px"}),
            dcc.Loading(
                id="offers-sa-loading",
                type="default",
                color=COLORS["purple"],
                children=html.Div(id="offers-sa-status"),
            ),
        ], style={
            "background": f"{COLORS['purple']}10", "border": f"1px solid {COLORS['purple']}30",
            "padding": "14px 18px", "borderRadius": "10px", "marginBottom": "20px",
        }),

        # Price check banner (fallback for offers without UPC)
        html.Div([
            html.Div([
                html.Div([
                    html.I(className="bi bi-currency-dollar",
                           style={"fontSize": "1.1rem", "color": COLORS["success"]}),
                ], style={"flexShrink": "0"}),
                html.Span(id="offers-price-pending-text",
                          children=f"Amazon price scraper: {no_price} without pricing",
                          style={"color": COLORS["text_muted"], "fontSize": "0.8rem", "flex": "1"}),
                styled_dropdown(
                    "offers-price-batch-size",
                    [{"label": f"{n}", "value": n} for n in [10, 25, 50]],
                    value=25,
                    clearable=False,
                ),
                html.Button([html.I(className="bi bi-search me-1"), "Price Check"],
                    id="offers-price-check-btn", className="btn-outline-dark",
                    style={"fontSize": "0.75rem", "padding": "6px 12px", "whiteSpace": "nowrap"}),
            ], style={"display": "flex", "alignItems": "center", "gap": "12px"}),
            html.Div(id="offers-price-status"),
        ], style={
            "background": f"{COLORS['card']}", "border": f"1px solid {COLORS['card_border']}",
            "padding": "10px 14px", "borderRadius": "8px", "marginBottom": "20px",
        }),

        # Main data table
        html.Div([
            dash_table.DataTable(
                id="offers-main-table",
                columns=TABLE_COLUMNS,
                data=table_data,
                style_header={
                    "backgroundColor": COLORS["sidebar"],
                    "color": COLORS["text"],
                    "fontWeight": "600",
                    "border": f"1px solid {COLORS['card_border']}",
                    "fontSize": "0.8rem",
                    "padding": "10px 14px",
                    "whiteSpace": "normal",
                },
                style_cell={
                    "backgroundColor": COLORS["card"],
                    "color": COLORS["text"],
                    "border": f"1px solid {COLORS['card_border']}",
                    "fontSize": "0.82rem",
                    "padding": "8px 14px",
                    "textAlign": "left",
                    "maxWidth": "200px",
                    "overflow": "hidden",
                    "textOverflow": "ellipsis",
                },
                style_data_conditional=[
                    {"if": {"state": "active"},
                     "backgroundColor": COLORS["hover"],
                     "border": f"1px solid {COLORS['primary']}"},
                    {"if": {"state": "selected"},
                     "backgroundColor": COLORS["hover"],
                     "border": f"1px solid {COLORS['primary']}"},
                ] + _status_conditional_styles(),
                style_filter={
                    "backgroundColor": COLORS["input_bg"],
                    "color": COLORS["text"],
                },
                style_table={"overflowX": "auto"},
                page_size=20,
                page_action="native",
                sort_action="native",
                sort_mode="multi",
                filter_action="native",
                row_selectable="single",
                selected_rows=[],
            ),
        ], className="dash-card", style={"marginBottom": "24px", "padding": "0", "overflow": "hidden"}),

        # Detail / Status update panel (hidden by default)
        html.Div(id="offers-detail-panel", style={"marginBottom": "24px"}),

        # Add Offer form
        html.Div([
            html.Div([
                html.Div([
                    html.I(className="bi bi-plus-circle",
                           style={"fontSize": "1.3rem", "color": COLORS["primary"]}),
                ], style={
                    "width": "42px", "height": "42px", "borderRadius": "10px",
                    "background": f"{COLORS['primary']}15", "display": "flex",
                    "alignItems": "center", "justifyContent": "center", "flexShrink": "0",
                }),
                html.Div([
                    html.H5("Add New Offer", style={"marginBottom": "2px", "color": COLORS["text"]}),
                    html.P("Manually enter a new inventory offer",
                           style={"color": COLORS["text_muted"], "fontSize": "0.8rem",
                                  "marginBottom": "0"}),
                ]),
            ], style={"display": "flex", "gap": "14px", "alignItems": "center",
                      "marginBottom": "20px"}),

            # Form fields row 1
            html.Div([
                form_group("UPC",
                           styled_input("offers-add-upc", "Enter UPC barcode", type="text")),
                form_group("Product Name",
                           styled_input("offers-add-name", "Product name", type="text")),
            ], className="grid-row grid-2"),

            # Form fields row 2
            html.Div([
                form_group("Category",
                           styled_dropdown("offers-add-category",
                                           [{"label": c, "value": c} for c in CATEGORIES],
                                           placeholder="Select category")),
                form_group("Quantity",
                           styled_input("offers-add-qty", "0", type="number")),
            ], className="grid-row grid-2"),

            # Form fields row 3
            html.Div([
                form_group("Offered Price ($)",
                           styled_input("offers-add-price", "0.00", type="number")),
                form_group("Expiry Date",
                           dcc.DatePickerSingle(
                               id="offers-add-expiry",
                               placeholder="Select expiry date",
                               className="dark-datepicker",
                               style={"width": "100%"},
                           )),
            ], className="grid-row grid-2"),

            # Form fields row 4
            html.Div([
                form_group("Source",
                           styled_dropdown("offers-add-source",
                                           [{"label": s, "value": s.lower().replace("-", "_")}
                                            for s in SOURCES],
                                           placeholder="Select source")),
                form_group("Notes",
                           styled_input("offers-add-notes", "Optional notes...", type="text")),
            ], className="grid-row grid-2"),

            # Submit
            html.Div([
                html.Button([
                    html.I(className="bi bi-plus-lg me-2"),
                    "Add Offer",
                ], id="offers-add-btn", className="btn-primary-dark",
                   style={"marginRight": "12px"}),
                html.Div(id="offers-add-status", style={"display": "inline-block"}),
            ], style={"marginTop": "8px"}),

        ], className="dash-card", style={"marginBottom": "24px"}),
    ])


# ── Callbacks ─────────────────────────────────────────────────────────────────

@callback(
    Output("offers-active-filter", "data"),
    Input("offers-filter-all", "n_clicks"),
    Input("offers-filter-new", "n_clicks"),
    Input("offers-filter-evaluating", "n_clicks"),
    Input("offers-filter-matched", "n_clicks"),
    Input("offers-filter-accepted", "n_clicks"),
    Input("offers-filter-rejected", "n_clicks"),
    prevent_initial_call=True,
)
def _set_filter(*args):
    """Track which status filter button was clicked."""
    triggered = ctx.triggered_id or ""
    if isinstance(triggered, str) and triggered.startswith("offers-filter-"):
        return triggered.replace("offers-filter-", "")
    return "all"


@callback(
    Output("offers-main-table", "data"),
    Output("offers-kpi-row", "children"),
    Input("offers-active-filter", "data"),
    Input("offers-category-filter", "value"),
    Input("offers-add-btn", "n_clicks"),
    prevent_initial_call=True,
)
def _update_table(status_filter, category_filter, _add_click):
    """Re-render the table and KPIs when filters change or data is added."""
    offers = _load_offers()
    status_filter = status_filter or "all"
    table_data = _build_table_data(offers, status_filter, category_filter)
    kpi_row = _build_kpi_row(offers)
    return table_data, kpi_row


@callback(
    Output("offers-add-status", "children"),
    Output("offers-add-upc", "value"),
    Output("offers-add-name", "value"),
    Output("offers-add-category", "value"),
    Output("offers-add-qty", "value"),
    Output("offers-add-price", "value"),
    Output("offers-add-expiry", "date"),
    Output("offers-add-source", "value"),
    Output("offers-add-notes", "value"),
    Input("offers-add-btn", "n_clicks"),
    State("offers-add-upc", "value"),
    State("offers-add-name", "value"),
    State("offers-add-category", "value"),
    State("offers-add-qty", "value"),
    State("offers-add-price", "value"),
    State("offers-add-expiry", "date"),
    State("offers-add-source", "value"),
    State("offers-add-notes", "value"),
    prevent_initial_call=True,
)
def _add_offer(n_clicks, upc, name, category, qty, price, expiry, source, notes):
    """Add a new offer to the JSON data file."""
    if not n_clicks:
        return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update

    # Validation
    errors = []
    if not upc or not str(upc).strip():
        errors.append("UPC")
    if not name or not str(name).strip():
        errors.append("Product Name")
    if not category:
        errors.append("Category")
    if not qty or (isinstance(qty, (int, float)) and qty <= 0):
        errors.append("Quantity (must be > 0)")
    if price is None or (isinstance(price, (int, float)) and price <= 0):
        errors.append("Offered Price (must be > 0)")

    if errors:
        msg = html.Span([
            html.I(className="bi bi-exclamation-triangle me-2",
                   style={"color": COLORS["danger"]}),
            f"Missing required fields: {', '.join(errors)}",
        ], style={"color": COLORS["danger"], "fontSize": "0.85rem"})
        return msg, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update

    try:
        offers = _load_offers()
        new_offer = {
            "id": _next_id(offers),
            "upc": str(upc).strip(),
            "product_name": str(name).strip(),
            "category": category,
            "quantity": int(qty),
            "offered_price": round(float(price), 2),
            "expiry": expiry or "",
            "source": (source or "other").lower(),
            "source_from": "",
            "status": "new",
            "marketplace_data": {
                "amazon_price": None,
                "walmart_price": None,
            },
            "matched_buyers": [],
            "margin_pct": None,
            "created_at": datetime.now().isoformat(),
            "notes": str(notes or "").strip(),
        }
        offers.append(new_offer)
        _save_offers(offers)

        msg = html.Span([
            html.I(className="bi bi-check-circle-fill me-2",
                   style={"color": COLORS["success"]}),
            f"Offer #{new_offer['id']} added: {new_offer['product_name']}",
        ], style={"color": COLORS["success"], "fontSize": "0.85rem"})
        # Clear form fields
        return msg, "", "", None, None, None, None, None, ""

    except Exception as e:
        msg = html.Span([
            html.I(className="bi bi-x-circle-fill me-2",
                   style={"color": COLORS["danger"]}),
            f"Error saving offer: {str(e)}",
        ], style={"color": COLORS["danger"], "fontSize": "0.85rem"})
        return msg, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update


@callback(
    Output("offers-detail-panel", "children"),
    Output("offers-selected-id", "data"),
    Input("offers-main-table", "selected_rows"),
    State("offers-main-table", "data"),
    prevent_initial_call=True,
)
def _show_detail(selected_rows, table_data):
    """Show detail panel when a row is selected."""
    if not selected_rows or not table_data:
        return html.Div(), None

    row_idx = selected_rows[0]
    if row_idx >= len(table_data):
        return html.Div(), None

    row = table_data[row_idx]
    offer_id = row.get("id")

    # Load full offer data from file
    offers = _load_offers()
    offer = next((o for o in offers if o.get("id") == offer_id), None)
    if not offer:
        return html.Div(), None

    status = offer.get("status", "new")
    status_color = STATUS_COLORS.get(status, COLORS["text_muted"])
    mp = offer.get("marketplace_data") or {}
    sa = offer.get("sa_data") or {}
    buyers = offer.get("matched_buyers") or []

    buyer_list = html.Div([
        html.Div([
            html.Span(b.get("buyer_name", "Unknown"), style={
                "color": COLORS["text"], "fontWeight": "500",
            }),
            html.Span(f" (Fit: {b.get('fit_score', 'N/A')})", style={
                "color": COLORS["text_muted"], "fontSize": "0.8rem",
            }),
        ], style={"marginBottom": "4px"})
        for b in buyers
    ]) if buyers else html.Span("No matched buyers yet", style={
        "color": COLORS["text_muted"], "fontSize": "0.85rem",
    })

    detail = html.Div([
        # Header row
        html.Div([
            html.Div([
                html.Div([
                    html.I(className="bi bi-box-seam",
                           style={"fontSize": "1.3rem", "color": COLORS["primary"]}),
                ], style={
                    "width": "42px", "height": "42px", "borderRadius": "10px",
                    "background": f"{COLORS['primary']}15", "display": "flex",
                    "alignItems": "center", "justifyContent": "center", "flexShrink": "0",
                }),
                html.Div([
                    html.H5(offer.get("product_name", "Unknown"),
                            style={"marginBottom": "2px", "color": COLORS["text"]}),
                    html.Div([
                        html.Span(STATUS_LABELS.get(status, status),
                                  style=_status_pill_style(status)),
                        html.Span(f"  ID: #{offer_id}", style={
                            "color": COLORS["text_muted"], "fontSize": "0.8rem",
                            "marginLeft": "12px",
                        }),
                    ]),
                ]),
            ], style={"display": "flex", "gap": "14px", "alignItems": "center"}),
            html.Button([
                html.I(className="bi bi-x-lg"),
            ], id="offers-detail-close", n_clicks=0, style={
                "background": "transparent", "border": "none",
                "color": COLORS["text_muted"], "cursor": "pointer",
                "fontSize": "1.1rem",
            }),
        ], style={"display": "flex", "justifyContent": "space-between",
                  "alignItems": "flex-start", "marginBottom": "20px"}),

        # Detail grid
        html.Div([
            # Left column: offer + SA details
            html.Div([
                # Our pricing
                html.H6("Our Pricing", style={"color": COLORS["text_muted"], "fontSize": "0.75rem",
                         "textTransform": "uppercase", "letterSpacing": "0.05em", "marginBottom": "8px"}),
                _detail_field("Supplier Case Price", _format_currency(offer.get("offered_price"))),
                _detail_field("Pack Qty", str(offer.get("pack_qty", "")) or "-"),
                _detail_field("Our Cost/Unit", _format_currency(offer.get("per_unit_cost"))),
                _detail_field("Our Wholesale Price", _format_currency(offer.get("wholesale_price"))),
                _detail_field("Our Margin", f"{offer.get('our_margin_pct', 0) or sa.get('our_margin_pct', 0):.1f}%"),

                html.Hr(style={"borderColor": COLORS["card_border"], "margin": "12px 0"}),

                # Amazon market data (for buyer evaluation)
                html.H6("Amazon Market Data", style={"color": COLORS["text_muted"], "fontSize": "0.75rem",
                         "textTransform": "uppercase", "letterSpacing": "0.05em", "marginBottom": "8px"}),
                _detail_field("ASIN", sa.get("asin", "") or "-"),
                _detail_field("Buy Box Price", _format_currency(sa.get("buy_box_price") or mp.get("amazon_price"))),
                _detail_field("FBA Fees", _format_currency(sa.get("total_fees"))),
                _detail_field("Buyer Profit/Unit", _format_currency(sa.get("buyer_profit"))),
                _detail_field("Buyer ROI", f"{sa.get('buyer_roi_pct', 0):.1f}%" if sa.get("buyer_roi_pct") else "-"),
                _detail_field("Mo. Sales", str(sa.get("estimated_monthly_sales", "")) or "-"),
                _detail_field("BSR", f"{sa.get('bsr', '')} (top {sa.get('bsr_top_pct', '')}%)" if sa.get("bsr") else "-"),
                _detail_field("FBA Sellers", str(sa.get("fba_sellers", "")) or "-"),

                html.Hr(style={"borderColor": COLORS["card_border"], "margin": "12px 0"}),

                _detail_field("UPC", offer.get("upc", "")),
                _detail_field("Category", offer.get("category", "")),
                _detail_field("Available", str(offer.get("quantity", 0))),
                _detail_field("Expiry", _format_date(offer.get("expiry", ""))),
                _detail_field("Source", (offer.get("source") or "").capitalize()),
                _detail_field("From", offer.get("source_from", "") or "-"),
                # Amazon link
                html.Div([
                    html.A([html.I(className="bi bi-box-arrow-up-right me-2"), "View on Amazon"],
                           href=sa.get("product_url") or f"https://www.amazon.com/s?k={offer.get('upc', '')}",
                           target="_blank",
                           style={"color": COLORS["primary"], "fontSize": "0.85rem",
                                  "textDecoration": "none"}),
                ], style={"marginTop": "8px"}) if sa.get("product_url") or offer.get("upc") else None,
            ], style={"flex": "1"}),

            # Right column: buyers and status update
            html.Div([
                html.H6("Matched Buyers", style={
                    "color": COLORS["text"], "fontWeight": "600",
                    "fontSize": "0.9rem", "marginBottom": "12px",
                }),
                buyer_list,

                html.Hr(style={"borderColor": COLORS["card_border"], "margin": "20px 0"}),

                html.H6("Update Status", style={
                    "color": COLORS["text"], "fontWeight": "600",
                    "fontSize": "0.9rem", "marginBottom": "12px",
                }),
                styled_dropdown(
                    "offers-status-update",
                    [{"label": STATUS_LABELS[s], "value": s} for s in STATUSES],
                    value=status,
                    placeholder="Select status",
                ),
                html.Button([
                    html.I(className="bi bi-check2 me-2"),
                    "Update Status",
                ], id="offers-status-save-btn", className="btn-primary-dark",
                   style={"marginTop": "12px", "width": "100%"}),
                html.Div(id="offers-status-save-msg", style={"marginTop": "8px"}),
            ], style={"flex": "1", "minWidth": "240px"}),
        ], style={
            "display": "flex", "gap": "32px", "flexWrap": "wrap",
        }),
    ], className="dash-card", style={
        "border": f"1px solid {status_color}40",
    })

    return detail, offer_id


def _detail_field(label, value):
    """Render a label: value row in the detail panel."""
    return html.Div([
        html.Span(f"{label}: ", style={
            "color": COLORS["text_muted"], "fontSize": "0.82rem",
            "fontWeight": "500", "minWidth": "110px", "display": "inline-block",
        }),
        html.Span(str(value), style={
            "color": COLORS["text"], "fontSize": "0.85rem",
        }),
    ], style={"marginBottom": "8px", "display": "flex", "alignItems": "baseline"})


@callback(
    Output("offers-status-save-msg", "children"),
    Input("offers-status-save-btn", "n_clicks"),
    State("offers-status-update", "value"),
    State("offers-selected-id", "data"),
    prevent_initial_call=True,
)
def _update_status(n_clicks, new_status, offer_id):
    """Update the status of the selected offer."""
    if not n_clicks or not offer_id or not new_status:
        return no_update

    try:
        offers = _load_offers()
        found = False
        for o in offers:
            if o.get("id") == offer_id:
                o["status"] = new_status
                found = True
                break

        if not found:
            return html.Span([
                html.I(className="bi bi-x-circle-fill me-2",
                       style={"color": COLORS["danger"]}),
                f"Offer #{offer_id} not found",
            ], style={"color": COLORS["danger"], "fontSize": "0.85rem"})

        _save_offers(offers)
        color = STATUS_COLORS.get(new_status, COLORS["text_muted"])
        return html.Span([
            html.I(className="bi bi-check-circle-fill me-2",
                   style={"color": COLORS["success"]}),
            f"Status updated to {STATUS_LABELS.get(new_status, new_status)}",
        ], style={"color": COLORS["success"], "fontSize": "0.85rem"})

    except Exception as e:
        return html.Span([
            html.I(className="bi bi-x-circle-fill me-2",
                   style={"color": COLORS["danger"]}),
            f"Error: {str(e)}",
        ], style={"color": COLORS["danger"], "fontSize": "0.85rem"})


@callback(
    Output("offers-price-status", "children"),
    Output("offers-price-pending-text", "children"),
    Input("offers-price-check-btn", "n_clicks"),
    State("offers-price-batch-size", "value"),
    prevent_initial_call=True,
)
def _run_price_check(n_clicks, batch_size):
    if not n_clicks:
        return no_update, no_update

    from utils.pricing import bulk_lookup_prices
    batch_size = int(batch_size or 25)

    try:
        result = bulk_lookup_prices(max_offers=batch_size, delay=1)
        found = result.get("amazon_found", 0)
        processed = result.get("processed", 0)
        remaining = result.get("remaining", 0)

        if found > 0:
            status = html.Div([
                html.I(className="bi bi-check-circle-fill me-2",
                       style={"color": COLORS["success"]}),
                html.Span(
                    f"Found {found} Amazon price{'s' if found != 1 else ''} "
                    f"out of {processed} checked. {remaining} still pending.",
                    style={"color": COLORS["success"], "fontWeight": "500",
                           "fontSize": "0.85rem"}),
            ], style={
                "background": f"{COLORS['success']}10", "padding": "10px 14px",
                "borderRadius": "8px", "marginTop": "12px",
            })
        else:
            status = html.Div([
                html.I(className="bi bi-info-circle me-2",
                       style={"color": COLORS["info"]}),
                html.Span(
                    f"Checked {processed} offers, no new prices found. {remaining} still pending.",
                    style={"color": COLORS["text_muted"], "fontSize": "0.85rem"}),
            ], style={
                "background": f"{COLORS['info']}10", "padding": "10px 14px",
                "borderRadius": "8px", "marginTop": "12px",
            })

        return status, f"— {remaining} offers without pricing"

    except Exception as e:
        return html.Div([
            html.I(className="bi bi-x-circle-fill me-2",
                   style={"color": COLORS["danger"]}),
            html.Span(f"Error: {str(e)}",
                      style={"color": COLORS["danger"], "fontSize": "0.85rem"}),
        ], style={
            "padding": "10px 14px", "borderRadius": "8px", "marginTop": "12px",
            "background": f"{COLORS['danger']}10",
        }), no_update


@callback(
    Output("offers-sa-status", "children"),
    Output("offers-sa-pending-text", "children"),
    Input("offers-sa-enrich-btn", "n_clicks"),
    State("offers-sa-batch-size", "value"),
    prevent_initial_call=True,
)
def _run_sa_enrichment(n_clicks, batch_size):
    if not n_clicks:
        return no_update, no_update

    from utils.seller_assistant import bulk_enrich
    batch_size = int(batch_size or 25)

    try:
        result = bulk_enrich(max_offers=batch_size, delay=1.1)
        enriched = result.get("enriched", 0)
        restricted = result.get("restricted", 0)
        errors = result.get("errors", 0)
        remaining = result.get("remaining", 0)

        parts = []
        if enriched:
            parts.append(f"{enriched} enriched")
        if restricted:
            parts.append(f"{restricted} restricted")
        if errors:
            parts.append(f"{errors} errors")
        detail = ", ".join(parts) if parts else "nothing to process"

        status = html.Div([
            html.I(className="bi bi-check-circle-fill me-2",
                   style={"color": COLORS["success"]}),
            html.Span(f"{detail}. {remaining} remaining.",
                      style={"color": COLORS["success"], "fontWeight": "500",
                             "fontSize": "0.85rem"}),
        ], style={
            "background": f"{COLORS['success']}10", "padding": "10px 14px",
            "borderRadius": "8px", "marginTop": "12px",
        })

        return status, f"— {remaining} offers need enrichment"

    except Exception as e:
        return html.Div([
            html.I(className="bi bi-x-circle-fill me-2",
                   style={"color": COLORS["danger"]}),
            html.Span(f"Error: {str(e)}",
                      style={"color": COLORS["danger"], "fontSize": "0.85rem"}),
        ], style={
            "padding": "10px 14px", "borderRadius": "8px", "marginTop": "12px",
            "background": f"{COLORS['danger']}10",
        }), no_update
