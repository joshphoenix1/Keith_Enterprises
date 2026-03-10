import json
import os
from datetime import datetime, date

from dash import html, dcc, callback, Input, Output, State, dash_table, no_update, ctx, ALL
from config import COLORS
from components.cards import kpi_card
from components.forms import styled_input, styled_dropdown, form_group

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "offers.json")

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
        id={"type": "offers-filter-btn", "index": status_value},
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
        buyers = o.get("matched_buyers") or []
        buyer_name = buyers[0]["buyer_name"] if buyers else "-"
        rows.append({
            "id": o.get("id"),
            "status": STATUS_LABELS.get(o.get("status", ""), o.get("status", "")),
            "product_name": o.get("product_name", ""),
            "upc": o.get("upc", ""),
            "category": o.get("category", ""),
            "quantity": o.get("quantity", 0),
            "offered_price": _format_currency(o.get("offered_price")),
            "amazon_price": _format_currency(mp.get("amazon_price")),
            "walmart_price": _format_currency(mp.get("walmart_price")),
            "margin_pct": _format_pct(o.get("margin_pct")),
            "matched_buyer": buyer_name,
            "source": (o.get("source") or "").capitalize(),
            "expiry": _format_date(o.get("expiry", "")),
            "date_added": _format_date(o.get("created_at", "")),
        })
    return rows


TABLE_COLUMNS = [
    {"name": "Status", "id": "status"},
    {"name": "Product Name", "id": "product_name"},
    {"name": "UPC", "id": "upc"},
    {"name": "Category", "id": "category"},
    {"name": "Qty", "id": "quantity", "type": "numeric"},
    {"name": "Offered Price", "id": "offered_price"},
    {"name": "Amazon Price", "id": "amazon_price"},
    {"name": "Walmart Price", "id": "walmart_price"},
    {"name": "Margin %", "id": "margin_pct"},
    {"name": "Matched Buyer", "id": "matched_buyer"},
    {"name": "Source", "id": "source"},
    {"name": "Expiry", "id": "expiry"},
    {"name": "Date Added", "id": "date_added"},
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
    Input({"type": "offers-filter-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def _set_filter(n_clicks_list):
    """Track which status filter button was clicked."""
    triggered = ctx.triggered_id
    if triggered and isinstance(triggered, dict):
        return triggered["index"]
    return "all"


@callback(
    Output("offers-main-table", "data"),
    Output("offers-kpi-row", "children"),
    Output({"type": "offers-filter-btn", "index": ALL}, "style"),
    Input("offers-active-filter", "data"),
    Input("offers-category-filter", "value"),
    Input("offers-add-btn", "n_clicks"),
    Input("offers-main-table", "data_timestamp"),
)
def _update_table(status_filter, category_filter, _add_click, _ts):
    """Re-render the table and KPIs when filters change or data is added."""
    offers = _load_offers()
    status_filter = status_filter or "all"
    table_data = _build_table_data(offers, status_filter, category_filter)
    kpi_row = _build_kpi_row(offers)

    # Build button styles based on active filter
    filter_values = ["all", "new", "evaluating", "matched", "accepted", "rejected"]
    button_styles = []
    for val in filter_values:
        is_active = (val == status_filter)
        if is_active:
            button_styles.append({
                "background": COLORS["active"],
                "color": "#ffffff",
                "border": f"1px solid {COLORS['active']}",
                "borderRadius": "6px",
                "padding": "6px 16px",
                "fontSize": "0.8rem",
                "fontWeight": "500",
                "cursor": "pointer",
                "transition": "all 0.15s ease",
            })
        else:
            button_styles.append({
                "background": "transparent",
                "color": COLORS["text_muted"],
                "border": f"1px solid {COLORS['card_border']}",
                "borderRadius": "6px",
                "padding": "6px 16px",
                "fontSize": "0.8rem",
                "fontWeight": "500",
                "cursor": "pointer",
                "transition": "all 0.15s ease",
            })

    return table_data, kpi_row, button_styles


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
            # Left column: offer details
            html.Div([
                _detail_field("UPC", offer.get("upc", "")),
                _detail_field("Category", offer.get("category", "")),
                _detail_field("Quantity", str(offer.get("quantity", 0))),
                _detail_field("Offered Price", _format_currency(offer.get("offered_price"))),
                _detail_field("Amazon Price", _format_currency(mp.get("amazon_price"))),
                _detail_field("Walmart Price", _format_currency(mp.get("walmart_price"))),
                _detail_field("Margin", _format_pct(offer.get("margin_pct"))),
                _detail_field("Expiry", _format_date(offer.get("expiry", ""))),
                _detail_field("Source", (offer.get("source") or "").capitalize()),
                _detail_field("From", offer.get("source_from", "") or "-"),
                _detail_field("Added", _format_date(offer.get("created_at", ""))),
                _detail_field("Notes", offer.get("notes", "") or "-"),
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
