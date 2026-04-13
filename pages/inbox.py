import json
import os
import base64
from dash import html, dcc, callback, Input, Output, State, ALL, ctx
from config import COLORS
from components.cards import info_card
from utils.vision import analyze_image, analyze_multiple_images, save_scan_result

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DATA_PATH = os.path.join(DATA_DIR, "inbox.json")
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

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


def _load_inbox():
    try:
        with open(DATA_PATH) as f:
            return json.load(f)
    except Exception:
        return {"messages": []}


def _save_inbox(data):
    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _source_badge(source):
    if source == "email":
        return html.Span([
            html.I(className="bi bi-envelope-fill me-1"), "Email",
        ], style={
            "background": f"{COLORS['primary']}20", "color": COLORS["primary"],
            "padding": "3px 10px", "borderRadius": "12px", "fontSize": "0.75rem",
            "fontWeight": "600",
        })
    else:
        return html.Span([
            html.I(className="bi bi-whatsapp me-1"), "WhatsApp",
        ], style={
            "background": "#25D36620", "color": "#25D366",
            "padding": "3px 10px", "borderRadius": "12px", "fontSize": "0.75rem",
            "fontWeight": "600",
        })


def _attachment_badges(attachments, scanned):
    if not attachments:
        return None
    img_count = sum(1 for a in attachments if a.get("type") == "image")
    if img_count == 0:
        return None

    color = COLORS["success"] if scanned else COLORS["purple"]
    icon = "bi-check-circle" if scanned else "bi-camera"
    label = f"{img_count} image{'s' if img_count != 1 else ''}" + (" scanned" if scanned else "")

    return html.Span([
        html.I(className=f"bi {icon} me-1"),
        label,
    ], style={
        "background": f"{color}20", "color": color,
        "padding": "2px 8px", "borderRadius": "10px", "fontSize": "0.7rem",
        "fontWeight": "600",
    })


def _message_card(msg):
    unread_dot = html.Span(style={
        "width": "8px", "height": "8px", "borderRadius": "50%",
        "background": COLORS["primary"], "display": "inline-block",
        "marginRight": "8px", "flexShrink": "0",
    }) if not msg["read"] else None

    product_count = len(msg.get("products", []))
    product_badge = html.Span(
        f"{product_count} product{'s' if product_count != 1 else ''}",
        style={
            "background": f"{COLORS['success']}20", "color": COLORS["success"],
            "padding": "2px 8px", "borderRadius": "10px", "fontSize": "0.7rem",
            "fontWeight": "600",
        },
    ) if product_count > 0 else None

    attachments = msg.get("attachments", [])
    scanned = msg.get("images_scanned", False)
    att_badge = _attachment_badges(attachments, scanned)

    # Scan button for messages with unscanned images
    has_images = any(a.get("type") == "image" for a in attachments)
    scan_btn = None
    if has_images and not scanned:
        scan_btn = html.Button([
            html.I(className="bi bi-camera me-1"),
            "Scan Images",
        ], id={"type": "inbox-scan-btn", "index": msg["id"]},
            className="btn-outline-dark",
            style={"fontSize": "0.7rem", "padding": "3px 10px", "marginTop": "6px"})
    elif has_images and scanned:
        scan_btn = html.Span([
            html.I(className="bi bi-check-circle-fill me-1",
                   style={"color": COLORS["success"]}),
            "Scanned",
        ], style={"color": COLORS["success"], "fontSize": "0.75rem", "marginTop": "6px",
                  "display": "inline-block"})

    # Scan results summary if available
    scan_results = msg.get("scan_results", [])
    scan_summary = None
    if scan_results:
        product_scans = [r for r in scan_results if r.get("is_product") and not r.get("skipped")]
        skipped_scans = [r for r in scan_results if r.get("skipped") or r.get("is_product") is False]
        parts = []
        if product_scans:
            names = [r.get("product_name", "Unknown") for r in product_scans]
            parts.append(html.Div([
                html.I(className="bi bi-cpu me-1", style={"color": COLORS["purple"]}),
                html.Span(f"AI extracted: {', '.join(names)}",
                          style={"color": COLORS["text_muted"], "fontSize": "0.75rem"}),
            ]))
        if skipped_scans:
            parts.append(html.Div([
                html.I(className="bi bi-funnel me-1", style={"color": COLORS["text_muted"]}),
                html.Span(f"{len(skipped_scans)} non-product image{'s' if len(skipped_scans) != 1 else ''} filtered out",
                          style={"color": COLORS["text_muted"], "fontSize": "0.7rem"}),
            ]))
        scan_summary = html.Div(parts, style={"marginTop": "6px"})

    return html.Div([
        # Header row
        html.Div([
            html.Div([
                unread_dot,
                _source_badge(msg["source"]),
                html.Span(msg["from"], style={
                    "color": COLORS["text_muted"], "fontSize": "0.8rem", "marginLeft": "8px",
                }),
            ], style={"display": "flex", "alignItems": "center"}),
            html.Div([
                att_badge,
                product_badge,
                html.Span(msg["date"], style={
                    "color": COLORS["text_muted"], "fontSize": "0.75rem", "marginLeft": "8px",
                }),
            ], style={"display": "flex", "alignItems": "center", "gap": "8px"}),
        ], style={"display": "flex", "justifyContent": "space-between",
                  "alignItems": "center", "marginBottom": "8px"}),
        # Subject
        html.Div(msg["subject"], style={
            "color": COLORS["text"], "fontWeight": "600" if not msg["read"] else "400",
            "fontSize": "0.9rem", "marginBottom": "4px",
        }),
        # Preview
        html.P(msg["body"][:150] + ("..." if len(msg["body"]) > 150 else ""), style={
            "color": COLORS["text_muted"], "fontSize": "0.8rem", "marginBottom": "0",
            "lineHeight": "1.4",
        }),
        # Scan button + results
        html.Div([scan_btn, scan_summary], style={"display": "flex", "gap": "12px",
                                                    "alignItems": "center", "flexWrap": "wrap"})
        if (scan_btn or scan_summary) else None,
        # WhatsApp reply input
        html.Div([
            dcc.Input(
                id={"type": "inbox-reply-input", "index": msg["id"]},
                type="text",
                placeholder="Type a reply...",
                style={
                    "flex": "1", "background": COLORS["input_bg"],
                    "border": f"1px solid {COLORS['card_border']}",
                    "borderRadius": "6px", "padding": "5px 10px",
                    "color": COLORS["text"], "fontSize": "0.8rem",
                    "outline": "none",
                },
                debounce=False,
            ),
            html.Button([
                html.I(className="bi bi-send-fill me-1"),
                "Send",
            ], id={"type": "inbox-reply-btn", "index": msg["id"]},
                className="btn-primary-dark",
                style={
                    "fontSize": "0.75rem", "padding": "5px 12px",
                    "whiteSpace": "nowrap",
                }),
        ], style={
            "display": "flex", "gap": "8px", "alignItems": "center",
            "marginTop": "8px", "paddingTop": "8px",
            "borderTop": f"1px solid {COLORS['card_border']}",
        }) if msg["source"] == "whatsapp" else None,
    ], style={
        "padding": "14px 16px",
        "borderBottom": f"1px solid {COLORS['card_border']}",
        "background": f"{COLORS['primary']}05" if not msg["read"] else "transparent",
        "transition": "background 0.15s",
    })


def _build_products_table(messages):
    """Extract all products from messages into a flat table."""
    rows = []
    for msg in messages:
        for p in msg.get("products", []):
            cat = p.get("category", "Other")
            rows.append({
                "product": p["name"],
                "upc": p.get("upc", ""),
                "category": cat,
                "price": f"${p['price_offered']:.2f}",
                "quantity": p.get("quantity", "—"),
                "expiry": p.get("expiry", "—"),
                "source": msg["source"].title(),
                "from": msg["from"],
                "date": msg["date"][:10],
                "status": "New",
            })
        # Also include products found by image scanning
        for r in msg.get("scan_results", []):
            if r.get("is_product") and not r.get("skipped") and r.get("product_name"):
                rows.append({
                    "product": r["product_name"],
                    "upc": "",
                    "category": "Other",
                    "price": "—",
                    "quantity": "—",
                    "expiry": "—",
                    "source": f"{msg['source'].title()} (scan)",
                    "from": msg["from"],
                    "date": msg["date"][:10],
                    "status": "Scanned",
                })

    return rows


def _build_products_html_table(rows):
    """Build a styled HTML table for extracted products."""
    headers = ["Product", "UPC", "Category", "Price", "Qty", "Expiry", "Source", "From", "Date"]

    header_style = {
        "padding": "10px 12px",
        "textAlign": "left",
        "color": COLORS["text_muted"],
        "fontSize": "0.7rem",
        "fontWeight": "600",
        "textTransform": "uppercase",
        "letterSpacing": "0.05em",
        "borderBottom": f"1px solid {COLORS['card_border']}",
        "whiteSpace": "nowrap",
    }

    cell_style = {
        "padding": "9px 12px",
        "color": COLORS["text"],
        "fontSize": "0.8rem",
        "borderBottom": f"1px solid {COLORS['card_border']}",
        "whiteSpace": "nowrap",
    }

    thead = html.Thead(html.Tr([html.Th(h, style=header_style) for h in headers]))

    tbody_rows = []
    for row in rows:
        cat = row["category"]
        cat_color = CATEGORY_COLORS.get(cat, COLORS["text_muted"])
        cat_cell = html.Td(
            html.Span(cat, style={
                "background": f"{cat_color}20", "color": cat_color,
                "padding": "2px 8px", "borderRadius": "10px",
                "fontSize": "0.7rem", "fontWeight": "600",
            }),
            style=cell_style,
        )

        tr = html.Tr([
            html.Td(row["product"], style=cell_style),
            html.Td(row["upc"] or "—", style={**cell_style, "color": COLORS["text_muted"],
                                                 "fontSize": "0.75rem", "fontFamily": "monospace"}),
            cat_cell,
            html.Td(row["price"], style=cell_style),
            html.Td(str(row["quantity"]), style=cell_style),
            html.Td(str(row["expiry"])[:10] if row["expiry"] != "—" else "—", style=cell_style),
            html.Td(row["source"], style=cell_style),
            html.Td(row["from"], style=cell_style),
            html.Td(row["date"], style=cell_style),
        ])
        tbody_rows.append(tr)

    if not tbody_rows:
        return html.Div("No products extracted yet.",
                        style={"color": COLORS["text_muted"], "padding": "20px", "textAlign": "center"})

    table = html.Table(
        [thead, html.Tbody(tbody_rows)],
        style={
            "width": "100%",
            "borderCollapse": "collapse",
            "background": COLORS["card"],
            "borderRadius": "8px",
            "overflow": "hidden",
        },
    )

    return html.Div(table, style={"overflowX": "auto"})


def _build_kpi_row(messages, rows):
    """Build KPI summary row."""
    total_products = len(rows)
    total_msgs = len(messages)
    categories = set(r["category"] for r in rows if r["category"] != "Other")
    unread = sum(1 for m in messages if not m.get("read"))

    kpi_style = {
        "display": "flex",
        "gap": "16px",
        "marginBottom": "16px",
        "flexWrap": "wrap",
    }

    def _kpi(label, value, color):
        return html.Div([
            html.P(label, style={
                "color": COLORS["text_muted"], "fontSize": "0.7rem",
                "marginBottom": "2px", "textTransform": "uppercase",
                "letterSpacing": "0.05em", "fontWeight": "600",
            }),
            html.H5(value, style={
                "color": color, "fontWeight": "700", "marginBottom": "0",
                "fontSize": "1.1rem",
            }),
        ], style={
            "background": COLORS["card"],
            "border": f"1px solid {COLORS['card_border']}",
            "borderRadius": "8px",
            "padding": "12px 18px",
            "flex": "1",
            "minWidth": "140px",
        })

    return html.Div([
        _kpi("Products Found", str(total_products), COLORS["text"]),
        _kpi("Messages", str(total_msgs), COLORS["primary"]),
        _kpi("Categories", str(len(categories)), COLORS["purple"]),
        _kpi("Unread", str(unread), COLORS["info"] if unread else COLORS["text_muted"]),
    ], style=kpi_style)


def _count_unscanned(messages):
    return sum(1 for m in messages
               if not m.get("images_scanned") and
               any(a.get("type") == "image" for a in m.get("attachments", [])))


def layout():
    inbox = _load_inbox()
    messages = inbox.get("messages", [])

    total = len(messages)
    unread = sum(1 for m in messages if not m["read"])
    email_count = sum(1 for m in messages if m["source"] == "email")
    wa_count = sum(1 for m in messages if m["source"] == "whatsapp")
    total_products = sum(len(m.get("products", [])) for m in messages)
    imgs_with_attach = sum(1 for m in messages
                           if any(a.get("type") == "image" for a in m.get("attachments", [])))
    unscanned = _count_unscanned(messages)

    message_cards = [_message_card(m) for m in messages]
    rows = _build_products_table(messages)
    kpi_row = _build_kpi_row(messages, rows)
    products_html = _build_products_html_table(rows)

    # Filter buttons
    filter_bar = html.Div([
        html.Button([html.I(className="bi bi-inbox me-2"), f"All ({total})"],
                    id="inbox-filter-all", className="btn-primary-dark",
                    style={"fontSize": "0.8rem", "padding": "6px 14px", "marginRight": "8px"}),
        html.Button([html.I(className="bi bi-envelope me-2"), f"Email ({email_count})"],
                    id="inbox-filter-email", className="btn-outline-dark",
                    style={"fontSize": "0.8rem", "padding": "6px 14px", "marginRight": "8px"}),
        html.Button([html.I(className="bi bi-whatsapp me-2"), f"WhatsApp ({wa_count})"],
                    id="inbox-filter-wa", className="btn-outline-dark",
                    style={"fontSize": "0.8rem", "padding": "6px 14px", "marginRight": "8px"}),
        html.Button([html.I(className="bi bi-circle-fill me-2",
                           style={"fontSize": "0.5rem", "color": COLORS["primary"]}),
                     f"Unread ({unread})"],
                    id="inbox-filter-unread", className="btn-outline-dark",
                    style={"fontSize": "0.8rem", "padding": "6px 14px"}),
    ], style={"marginBottom": "16px"})

    return html.Div([
        html.Div([
            html.H2("Inbox"),
            html.P("Incoming inventory offers from WhatsApp and email"),
        ], className="page-header"),

        # Auto-scan pipeline banner
        html.Div([
            html.Div([
                html.Div([
                    html.I(className="bi bi-camera-fill",
                           style={"fontSize": "1.3rem", "color": COLORS["purple"]}),
                ], style={"flexShrink": "0"}),
                html.Div([
                    html.Span("Auto Image Scanning ",
                              style={"color": COLORS["text"], "fontWeight": "600"}),
                    html.Span("— Product images attached to messages are "
                              "automatically detected and scanned by Claude AI. Non-product images "
                              "(logos, signatures) are filtered out. Extracted products "
                              "appear in the table below.",
                              style={"color": COLORS["text_muted"]}),
                ], style={"fontSize": "0.85rem", "flex": "1"}),
                html.Div([
                    html.Button([
                        html.I(className="bi bi-play-circle me-2"),
                        f"Scan All ({unscanned} pending)",
                    ], id="inbox-scan-all-btn", className="btn-primary-dark",
                        style={"fontSize": "0.8rem", "padding": "8px 16px", "whiteSpace": "nowrap"},
                        disabled=unscanned == 0),
                ]),
            ], style={"display": "flex", "alignItems": "center", "gap": "16px"}),
        ], style={
            "background": f"{COLORS['purple']}10", "border": f"1px solid {COLORS['purple']}30",
            "padding": "14px 18px", "borderRadius": "10px", "marginBottom": "20px",
        }),

        # Reply status
        html.Div(id="inbox-reply-status"),

        # Scan status
        dcc.Loading(
            id="inbox-scan-loading",
            type="default",
            color=COLORS["primary"],
            children=html.Div(id="inbox-scan-status"),
        ),

        # Stats row
        html.Div([
            _stat_mini("Total Messages", str(total), "bi-chat-left-text", COLORS["primary"]),
            _stat_mini("Unread", str(unread), "bi-circle-fill", COLORS["info"]),
            _stat_mini("Products Found", str(total_products), "bi-tag", COLORS["success"]),
            _stat_mini("With Images", str(imgs_with_attach), "bi-image", COLORS["purple"]),
            _stat_mini("Pending Scan", str(unscanned), "bi-hourglass-split",
                       COLORS["warning"] if unscanned > 0 else COLORS["text_muted"]),
        ], className="grid-row grid-5"),

        # Two-column layout: messages + products table
        html.Div([
            html.Div([
                info_card("Messages", html.Div([
                    filter_bar,
                    html.Div(id="inbox-message-feed", children=message_cards,
                             style={"maxHeight": "600px", "overflowY": "auto",
                                    "border": f"1px solid {COLORS['card_border']}",
                                    "borderRadius": "8px"}),
                ]), "bi-chat-left-text"),
            ]),
            html.Div([
                info_card(f"Extracted Products ({len(rows)})",
                          html.Div([
                              html.Div([
                                  html.Div([
                                      html.I(className="bi bi-info-circle me-2",
                                             style={"color": COLORS["info"]}),
                                      html.Span("Products extracted from messages, URLs, and AI image scans.",
                                                style={"color": COLORS["text_muted"], "fontSize": "0.8rem",
                                                       "flex": "1"}),
                                      html.Button([
                                          html.I(className="bi bi-arrow-right-circle me-2"),
                                          "Push to Offers",
                                      ], id="inbox-push-offers-btn", className="btn-primary-dark",
                                         style={"fontSize": "0.8rem", "padding": "6px 14px",
                                                "whiteSpace": "nowrap"}),
                                  ], style={"display": "flex", "alignItems": "center", "gap": "12px"}),
                              ], style={
                                  "background": f"{COLORS['info']}10", "padding": "10px 14px",
                                  "borderRadius": "8px", "marginBottom": "16px",
                              }),
                              html.Div(id="inbox-push-status", style={"marginBottom": "12px"}),
                              html.Div(id="inbox-products-container",
                                       children=[kpi_row, products_html]),
                          ]), "bi-table"),
            ]),
        ], className="grid-row grid-2"),
    ])


def _stat_mini(label, value, icon, color):
    return html.Div([
        html.Div([
            html.I(className=f"bi {icon}",
                   style={"color": color, "fontSize": "1.1rem"}),
        ], style={
            "width": "36px", "height": "36px", "borderRadius": "10px",
            "background": f"{color}15", "display": "flex",
            "alignItems": "center", "justifyContent": "center",
        }),
        html.Div([
            html.P(label, style={"color": COLORS["text_muted"], "fontSize": "0.7rem",
                                 "marginBottom": "0"}),
            html.H5(value, style={"color": COLORS["text"], "fontWeight": "700",
                                  "marginBottom": "0"}),
        ]),
    ], className="dash-card",
       style={"display": "flex", "gap": "12px", "alignItems": "center", "padding": "14px 16px"})


def _scan_message_images(msg):
    """Scan all image attachments for a single message. Returns scan results."""
    attachments = msg.get("attachments", [])
    image_attachments = [a for a in attachments if a.get("type") == "image"]

    if not image_attachments:
        return []

    images = []
    for att in image_attachments:
        filepath = os.path.join(BASE_DIR, att["path"])
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                images.append({"bytes": f.read(), "filename": att["filename"]})

    if not images:
        return []

    if len(images) == 1:
        result = analyze_image(images[0]["bytes"], images[0]["filename"])
        result["filename"] = images[0]["filename"]
        save_scan_result(result, images[0]["filename"])
        return [result]
    else:
        results = analyze_multiple_images(images)
        for r in results:
            if r.get("is_product") and not r.get("skipped"):
                save_scan_result(r, r.get("filename", "unknown"))
        return results


# ── Callbacks ──

@callback(
    Output("inbox-message-feed", "children"),
    Input("inbox-filter-all", "n_clicks"),
    Input("inbox-filter-email", "n_clicks"),
    Input("inbox-filter-wa", "n_clicks"),
    Input("inbox-filter-unread", "n_clicks"),
    prevent_initial_call=True,
)
def filter_messages(all_clicks, email_clicks, wa_clicks, unread_clicks):
    inbox = _load_inbox()
    messages = inbox.get("messages", [])

    triggered = ctx.triggered_id
    if triggered == "inbox-filter-email":
        messages = [m for m in messages if m["source"] == "email"]
    elif triggered == "inbox-filter-wa":
        messages = [m for m in messages if m["source"] == "whatsapp"]
    elif triggered == "inbox-filter-unread":
        messages = [m for m in messages if not m["read"]]

    if not messages:
        return html.Div("No messages match this filter.",
                        style={"color": COLORS["text_muted"], "padding": "20px", "textAlign": "center"})

    return [_message_card(m) for m in messages]


@callback(
    Output("inbox-scan-status", "children"),
    Output("inbox-message-feed", "children", allow_duplicate=True),
    Output("inbox-products-container", "children"),
    Input("inbox-scan-all-btn", "n_clicks"),
    Input({"type": "inbox-scan-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def handle_scan(scan_all_clicks, individual_clicks):
    inbox = _load_inbox()
    messages = inbox.get("messages", [])

    triggered = ctx.triggered_id

    if triggered == "inbox-scan-all-btn":
        scanned_count = 0
        products_found = 0
        filtered_out = 0

        for msg in messages:
            if msg.get("images_scanned"):
                continue
            has_images = any(a.get("type") == "image" for a in msg.get("attachments", []))
            if not has_images:
                continue

            results = _scan_message_images(msg)
            msg["images_scanned"] = True
            msg["scan_results"] = results
            scanned_count += 1
            products_found += sum(1 for r in results if r.get("is_product") and not r.get("skipped"))
            filtered_out += sum(1 for r in results if r.get("skipped") or r.get("is_product") is False)

        _save_inbox(inbox)

        status = html.Div([
            html.I(className="bi bi-check-circle-fill me-2", style={"color": COLORS["success"]}),
            html.Span(f"Scanned {scanned_count} message{'s' if scanned_count != 1 else ''}. "
                      f"Found {products_found} product image{'s' if products_found != 1 else ''}, "
                      f"filtered out {filtered_out} non-product image{'s' if filtered_out != 1 else ''}.",
                      style={"color": COLORS["success"], "fontWeight": "500", "fontSize": "0.85rem"}),
        ], style={
            "background": f"{COLORS['success']}10", "padding": "12px 16px",
            "borderRadius": "8px", "marginBottom": "16px",
        })

    elif isinstance(triggered, dict) and triggered.get("type") == "inbox-scan-btn":
        msg_id = triggered["index"]
        msg = next((m for m in messages if m["id"] == msg_id), None)
        if msg and not msg.get("images_scanned"):
            results = _scan_message_images(msg)
            msg["images_scanned"] = True
            msg["scan_results"] = results
            _save_inbox(inbox)

            products_found = sum(1 for r in results if r.get("is_product") and not r.get("skipped"))
            status = html.Div([
                html.I(className="bi bi-check-circle-fill me-2", style={"color": COLORS["success"]}),
                html.Span(f"Scanned message from {msg['from']}. "
                          f"Found {products_found} product image{'s' if products_found != 1 else ''}.",
                          style={"color": COLORS["success"], "fontWeight": "500", "fontSize": "0.85rem"}),
            ], style={
                "background": f"{COLORS['success']}10", "padding": "12px 16px",
                "borderRadius": "8px", "marginBottom": "16px",
            })
        else:
            status = ""
    else:
        status = ""

    # Rebuild message feed and products table
    messages = _load_inbox().get("messages", [])
    message_cards = [_message_card(m) for m in messages]
    rows = _build_products_table(messages)
    kpi_row = _build_kpi_row(messages, rows)
    products_html = _build_products_html_table(rows)

    return status, message_cards, [kpi_row, products_html]


@callback(
    Output("inbox-push-status", "children"),
    Input("inbox-push-offers-btn", "n_clicks"),
    prevent_initial_call=True,
)
def push_to_offers(n_clicks):
    if not n_clicks:
        return ""
    try:
        from utils.pipeline import ingest_products_from_inbox
        result = ingest_products_from_inbox()
        new = result.get("new_offers", 0)
        dups = result.get("duplicates", 0)
        scanned = result.get("scanned", 0)
        if new > 0:
            return html.Div([
                html.I(className="bi bi-check-circle-fill me-2",
                       style={"color": COLORS["success"]}),
                html.Span(f"Created {new} new offer{'s' if new != 1 else ''} from {scanned} products "
                          f"({dups} duplicates skipped). ",
                          style={"color": COLORS["success"], "fontWeight": "500", "fontSize": "0.85rem"}),
                dcc.Link("View Offers →", href="/offers",
                         style={"color": COLORS["primary"], "fontSize": "0.85rem"}),
            ], style={"background": f"{COLORS['success']}10", "padding": "10px 14px",
                      "borderRadius": "8px"})
        else:
            return html.Div([
                html.I(className="bi bi-info-circle me-2",
                       style={"color": COLORS["info"]}),
                html.Span(f"No new products to create offers from ({scanned} scanned, {dups} already exist).",
                          style={"color": COLORS["text_muted"], "fontSize": "0.85rem"}),
            ], style={"background": f"{COLORS['info']}10", "padding": "10px 14px",
                      "borderRadius": "8px"})
    except Exception as e:
        return html.Div([
            html.I(className="bi bi-x-circle-fill me-2",
                   style={"color": COLORS["danger"]}),
            html.Span(f"Error: {e}", style={"color": COLORS["danger"], "fontSize": "0.85rem"}),
        ], style={"background": f"{COLORS['danger']}10", "padding": "10px 14px",
                  "borderRadius": "8px"})


@callback(
    Output("inbox-reply-status", "children"),
    Input({"type": "inbox-reply-btn", "index": ALL}, "n_clicks"),
    State({"type": "inbox-reply-input", "index": ALL}, "value"),
    prevent_initial_call=True,
)
def handle_whatsapp_reply(n_clicks_list, reply_texts):
    if not ctx.triggered_id or not isinstance(ctx.triggered_id, dict):
        return ""

    msg_id = ctx.triggered_id["index"]

    # Find which index in the pattern-matched lists corresponds to the triggered button
    triggered_idx = None
    for i, btn_id in enumerate(ctx.inputs_list[0]):
        if btn_id["id"]["index"] == msg_id:
            triggered_idx = i
            break

    if triggered_idx is None:
        return ""

    # Check that the button was actually clicked (not just initial load)
    if not n_clicks_list[triggered_idx]:
        return ""

    reply_text = reply_texts[triggered_idx]
    if not reply_text or not reply_text.strip():
        return html.Div([
            html.I(className="bi bi-exclamation-triangle-fill me-2",
                   style={"color": COLORS["danger"]}),
            html.Span("Please type a message before sending.",
                      style={"color": COLORS["danger"], "fontSize": "0.85rem"}),
        ], style={
            "background": f"{COLORS['danger']}10", "padding": "10px 14px",
            "borderRadius": "8px", "marginBottom": "12px",
        })

    # Look up the sender's phone number from the message
    inbox = _load_inbox()
    messages = inbox.get("messages", [])
    msg = next((m for m in messages if m["id"] == msg_id), None)
    if not msg:
        return html.Div([
            html.I(className="bi bi-x-circle-fill me-2",
                   style={"color": COLORS["danger"]}),
            html.Span("Message not found.",
                      style={"color": COLORS["danger"], "fontSize": "0.85rem"}),
        ], style={
            "background": f"{COLORS['danger']}10", "padding": "10px 14px",
            "borderRadius": "8px", "marginBottom": "12px",
        })

    try:
        from utils.whatsapp import send_message
        send_message(msg["from"], reply_text.strip())
        return html.Div([
            html.I(className="bi bi-check-circle-fill me-2",
                   style={"color": COLORS["success"]}),
            html.Span(f"Reply sent to {msg['from']}.",
                      style={"color": COLORS["success"], "fontSize": "0.85rem",
                             "fontWeight": "500"}),
        ], style={
            "background": f"{COLORS['success']}10", "padding": "10px 14px",
            "borderRadius": "8px", "marginBottom": "12px",
        })
    except Exception as e:
        return html.Div([
            html.I(className="bi bi-x-circle-fill me-2",
                   style={"color": COLORS["danger"]}),
            html.Span(f"Failed to send: {str(e)}",
                      style={"color": COLORS["danger"], "fontSize": "0.85rem"}),
        ], style={
            "background": f"{COLORS['danger']}10", "padding": "10px 14px",
            "borderRadius": "8px", "marginBottom": "12px",
        })
