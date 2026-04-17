import json
import os
from datetime import datetime

from dash import html, dcc, callback, Input, Output, State, dash_table, no_update, ctx
from config import COLORS
from components.cards import kpi_card
from components.forms import styled_input, styled_dropdown, form_group

from utils.orders import load_orders, save_orders, update_order_status

STATUS_LABELS = {
    "pending_review": "Pending Review",
    "confirmed": "Confirmed",
    "invoiced": "Invoiced",
    "paid": "Paid",
    "shipped": "Shipped",
    "completed": "Completed",
    "cancelled": "Cancelled",
}

STATUS_COLORS = {
    "pending_review": COLORS["warning"],
    "confirmed": COLORS["info"],
    "invoiced": COLORS["purple"],
    "paid": COLORS["success"],
    "shipped": COLORS["primary"],
    "completed": COLORS["success"],
    "cancelled": COLORS["danger"],
}


def _build_kpi_row(orders):
    total = len(orders)
    pending = sum(1 for o in orders if o.get("status") == "pending_review")
    confirmed = sum(1 for o in orders if o.get("status") in ("confirmed", "invoiced"))
    paid = sum(1 for o in orders if o.get("status") == "paid")
    total_value = sum(o.get("subtotal", 0) for o in orders if o.get("status") != "cancelled")

    def _kpi(icon, label, value, color):
        return html.Div([
            html.Div([
                html.Div([
                    html.I(className=f"bi {icon}", style={"fontSize": "1.5rem", "color": color}),
                ], style={
                    "width": "48px", "height": "48px", "borderRadius": "12px",
                    "background": f"{color}15", "display": "flex",
                    "alignItems": "center", "justifyContent": "center",
                }),
                html.Div([
                    html.P(label, className="mb-0", style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
                    html.H3(value, className="mb-0", style={"fontWeight": "700", "color": COLORS["text"]}),
                ]),
            ], style={"display": "flex", "gap": "16px", "alignItems": "center"}),
        ], className="dash-card")

    return html.Div([
        _kpi("bi-cart-check", "Total Orders", str(total), COLORS["primary"]),
        _kpi("bi-hourglass-split", "Pending Review", str(pending), COLORS["warning"]),
        _kpi("bi-check-circle", "Confirmed/Invoiced", str(confirmed), COLORS["info"]),
        _kpi("bi-currency-dollar", "Total Value", f"${total_value:,.0f}", COLORS["success"]),
    ], className="grid-row grid-4")


def _build_table_data(orders):
    rows = []
    for o in orders:
        items = o.get("items", [])
        rows.append({
            "id": o.get("id", ""),
            "buyer": o.get("buyer_name", ""),
            "items": len(items),
            "subtotal": round(o.get("subtotal", 0), 2),
            "status": STATUS_LABELS.get(o.get("status", ""), o.get("status", "")),
            "payment": o.get("payment_status", "unpaid").title(),
            "shipping": o.get("shipping_status", "not_shipped").replace("_", " ").title(),
            "created": o.get("created_at", "")[:16],
        })
    return rows


TABLE_COLUMNS = [
    {"name": "Order ID", "id": "id"},
    {"name": "Buyer", "id": "buyer"},
    {"name": "Items", "id": "items", "type": "numeric"},
    {"name": "Total", "id": "subtotal", "type": "numeric"},
    {"name": "Status", "id": "status"},
    {"name": "Payment", "id": "payment"},
    {"name": "Shipping", "id": "shipping"},
    {"name": "Created", "id": "created"},
]


def layout():
    orders = load_orders()
    table_data = _build_table_data(orders)

    return html.Div([
        dcc.Store(id="orders-selected-id", data=None),

        html.Div([
            html.H2("Orders"),
            html.P("Track and manage buyer orders through the fulfillment pipeline"),
        ], className="page-header"),

        html.Div(id="orders-kpi-row", children=_build_kpi_row(orders)),

        # Orders table
        html.Div([
            dash_table.DataTable(
                id="orders-main-table",
                columns=TABLE_COLUMNS,
                data=table_data,
                style_header={
                    "backgroundColor": COLORS["sidebar"],
                    "color": COLORS["text"],
                    "fontWeight": "600",
                    "border": f"1px solid {COLORS['card_border']}",
                    "fontSize": "0.8rem",
                    "padding": "10px 14px",
                },
                style_cell={
                    "backgroundColor": COLORS["card"],
                    "color": COLORS["text"],
                    "border": f"1px solid {COLORS['card_border']}",
                    "fontSize": "0.82rem",
                    "padding": "8px 14px",
                    "textAlign": "left",
                },
                style_data_conditional=[
                    {"if": {"state": "active"}, "backgroundColor": COLORS["hover"]},
                    {"if": {"state": "selected"}, "backgroundColor": COLORS["hover"]},
                ],
                style_table={"overflowX": "auto"},
                page_size=15,
                sort_action="native",
                row_selectable="single",
                selected_rows=[],
            ),
        ], className="dash-card", style={"marginBottom": "24px", "padding": "0", "overflow": "hidden"}),

        # Detail panel
        html.Div(id="orders-detail-panel"),

        # Action status
        html.Div(id="orders-action-status", style={"marginTop": "12px"}),
    ])


@callback(
    Output("orders-detail-panel", "children"),
    Output("orders-selected-id", "data"),
    Input("orders-main-table", "selected_rows"),
    State("orders-main-table", "data"),
    prevent_initial_call=True,
)
def _show_detail(selected_rows, table_data):
    if not selected_rows or not table_data:
        return html.Div(), None

    row = table_data[selected_rows[0]]
    order_id = row.get("id")
    orders = load_orders()
    order = next((o for o in orders if o.get("id") == order_id), None)
    if not order:
        return html.Div(), None

    status = order.get("status", "pending_review")
    status_color = STATUS_COLORS.get(status, COLORS["text_muted"])

    # Line items table
    items = order.get("items", [])
    item_rows = []
    for item in items:
        item_rows.append(html.Tr([
            html.Td(item.get("product_name", ""), style={"padding": "8px", "borderBottom": f"1px solid {COLORS['card_border']}"}),
            html.Td(item.get("upc", ""), style={"padding": "8px", "borderBottom": f"1px solid {COLORS['card_border']}", "color": COLORS["text_muted"], "fontFamily": "monospace", "fontSize": "0.8rem"}),
            html.Td(str(item.get("qty", 0)), style={"padding": "8px", "borderBottom": f"1px solid {COLORS['card_border']}", "textAlign": "center"}),
            html.Td(f"${item.get('unit_cost', 0):.2f}", style={"padding": "8px", "borderBottom": f"1px solid {COLORS['card_border']}", "textAlign": "right"}),
            html.Td(f"${item.get('line_total', 0):.2f}", style={"padding": "8px", "borderBottom": f"1px solid {COLORS['card_border']}", "textAlign": "right", "fontWeight": "600"}),
        ]))

    items_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Product", style={"padding": "8px", "textAlign": "left", "color": COLORS["text_muted"], "fontSize": "0.8rem"}),
            html.Th("UPC", style={"padding": "8px", "textAlign": "left", "color": COLORS["text_muted"], "fontSize": "0.8rem"}),
            html.Th("Qty", style={"padding": "8px", "textAlign": "center", "color": COLORS["text_muted"], "fontSize": "0.8rem"}),
            html.Th("Unit", style={"padding": "8px", "textAlign": "right", "color": COLORS["text_muted"], "fontSize": "0.8rem"}),
            html.Th("Total", style={"padding": "8px", "textAlign": "right", "color": COLORS["text_muted"], "fontSize": "0.8rem"}),
        ])),
        html.Tbody(item_rows),
    ], style={"width": "100%", "borderCollapse": "collapse"})

    def _field(label, value):
        return html.Div([
            html.Span(f"{label}: ", style={"color": COLORS["text_muted"], "fontSize": "0.82rem", "fontWeight": "500", "minWidth": "120px", "display": "inline-block"}),
            html.Span(str(value), style={"color": COLORS["text"], "fontSize": "0.85rem"}),
        ], style={"marginBottom": "6px"})

    # Status action buttons
    actions = []
    if status == "pending_review":
        actions.append(html.Button([html.I(className="bi bi-check-lg me-2"), "Confirm Order"],
                       id="orders-btn-confirm", className="btn-primary-dark", style={"marginRight": "8px"}))
        actions.append(html.Button([html.I(className="bi bi-x-lg me-2"), "Cancel"],
                       id="orders-btn-cancel", className="btn-outline-dark", style={"marginRight": "8px"}))
    elif status == "confirmed":
        actions.append(html.Button([html.I(className="bi bi-receipt me-2"), "Send Invoice"],
                       id="orders-btn-invoice", className="btn-primary-dark", style={"marginRight": "8px"}))
    elif status == "invoiced":
        actions.append(html.Button([html.I(className="bi bi-currency-dollar me-2"), "Mark Paid"],
                       id="orders-btn-paid", className="btn-primary-dark", style={"marginRight": "8px"}))
    elif status == "paid":
        actions.append(html.Button([html.I(className="bi bi-truck me-2"), "Mark Shipped"],
                       id="orders-btn-shipped", className="btn-primary-dark", style={"marginRight": "8px"}))
    elif status == "shipped":
        actions.append(html.Button([html.I(className="bi bi-check-circle me-2"), "Mark Complete"],
                       id="orders-btn-complete", className="btn-primary-dark", style={"marginRight": "8px"}))

    # Ensure all button IDs exist in DOM (Dash needs them for callback)
    for btn_id in ["orders-btn-confirm", "orders-btn-cancel", "orders-btn-invoice",
                    "orders-btn-paid", "orders-btn-shipped", "orders-btn-complete"]:
        if not any(getattr(a, 'id', None) == btn_id for a in actions):
            actions.append(html.Button(id=btn_id, style={"display": "none"}))

    detail = html.Div([
        html.Div([
            html.Div([
                html.H4(f"Order {order_id}", style={"margin": "0", "color": COLORS["text"]}),
                html.Span(STATUS_LABELS.get(status, status), style={
                    "background": f"{status_color}20", "color": status_color,
                    "padding": "3px 12px", "borderRadius": "12px", "fontSize": "0.8rem",
                    "fontWeight": "600", "marginLeft": "12px",
                }),
            ], style={"display": "flex", "alignItems": "center"}),
        ], style={"marginBottom": "16px"}),

        html.Div([
            html.Div([
                _field("Buyer", f"{order.get('buyer_name', '')} ({order.get('buyer_email', '')})"),
                _field("Created", order.get("created_at", "")),
                _field("Payment Terms", order.get("payment_terms", "Wire before ship")),
                _field("Payment Status", order.get("payment_status", "unpaid").title()),
                _field("Shipping", order.get("shipping_status", "not_shipped").replace("_", " ").title()),
                _field("Tracking", order.get("tracking_number", "") or "—"),
            ], style={"flex": "1"}),
            html.Div([
                html.Div(f"${order.get('subtotal', 0):,.2f}", style={
                    "fontSize": "2rem", "fontWeight": "700", "color": COLORS["success"],
                    "textAlign": "center",
                }),
                html.P("Order Total", style={"color": COLORS["text_muted"], "textAlign": "center",
                                               "fontSize": "0.85rem", "margin": "4px 0 16px"}),
                html.Div(actions, style={"display": "flex", "flexWrap": "wrap", "gap": "8px",
                                          "justifyContent": "center"}),
            ], style={"minWidth": "220px"}),
        ], style={"display": "flex", "gap": "32px", "flexWrap": "wrap", "marginBottom": "20px"}),

        html.H5("Line Items", style={"color": COLORS["text"], "marginBottom": "12px"}),
        html.Div(items_table, style={"overflowX": "auto"}),
    ], className="dash-card", style={"border": f"1px solid {status_color}40"})

    return detail, order_id


@callback(
    Output("orders-action-status", "children"),
    Output("orders-main-table", "data"),
    Output("orders-kpi-row", "children"),
    Output("orders-detail-panel", "children", allow_duplicate=True),
    Output("orders-selected-id", "data", allow_duplicate=True),
    Input("orders-btn-confirm", "n_clicks"),
    Input("orders-btn-cancel", "n_clicks"),
    Input("orders-btn-invoice", "n_clicks"),
    Input("orders-btn-paid", "n_clicks"),
    Input("orders-btn-shipped", "n_clicks"),
    Input("orders-btn-complete", "n_clicks"),
    State("orders-selected-id", "data"),
    prevent_initial_call=True,
)
def _handle_action(confirm, cancel, invoice, paid, shipped, complete, order_id):
    if not order_id:
        return no_update, no_update, no_update, no_update, no_update

    triggered = ctx.triggered_id
    if not triggered:
        return no_update, no_update, no_update, no_update, no_update

    action_map = {
        "orders-btn-confirm": ("confirmed", "Order confirmed"),
        "orders-btn-cancel": ("cancelled", "Order cancelled"),
        "orders-btn-paid": ("paid", "Payment recorded"),
        "orders-btn-shipped": ("shipped", "Marked as shipped"),
        "orders-btn-complete": ("completed", "Order completed"),
    }

    if triggered == "orders-btn-invoice":
        # Send invoice email
        orders = load_orders()
        order = next((o for o in orders if o.get("id") == order_id), None)
        if order:
            order["status"] = "invoiced"
            save_orders(orders)
            try:
                from utils.notifications import send_invoice_email
                send_invoice_email(order, order.get("buyer_email", ""), "")
            except Exception as e:
                pass
            msg = "Invoice sent to buyer"
        else:
            msg = "Order not found"
    elif triggered in action_map:
        new_status, msg = action_map[triggered]
        update_order_status(order_id, new_status)
    else:
        return no_update, no_update, no_update, no_update, no_update

    # Refresh everything
    orders = load_orders()
    table_data = _build_table_data(orders)
    kpi_row = _build_kpi_row(orders)

    # Re-render detail
    order = next((o for o in orders if o.get("id") == order_id), None)
    if order:
        detail, _ = _show_detail.__wrapped__(None, None)  # Can't easily call, just clear
    detail = html.Div()  # Clear detail panel to force re-select

    status_msg = html.Div([
        html.I(className="bi bi-check-circle-fill me-2", style={"color": COLORS["success"]}),
        html.Span(msg, style={"color": COLORS["success"], "fontSize": "0.85rem"}),
    ], style={"background": f"{COLORS['success']}10", "padding": "10px 14px", "borderRadius": "8px"})

    return status_msg, table_data, kpi_row, detail, None
