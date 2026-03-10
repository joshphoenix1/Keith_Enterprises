import json
import os
import base64
from dash import html, dcc, callback, Input, Output, State, ALL, ctx
from config import COLORS
from components.cards import info_card
from components.tables import dark_table
from utils.vision import analyze_image, analyze_multiple_images, save_scan_result
from utils.data import calc_feasibility, estimate_fba_fee, calc_referral_fee

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DATA_PATH = os.path.join(DATA_DIR, "inbox.json")
BASE_DIR = os.path.dirname(os.path.dirname(__file__))


def _load_inbox():
    with open(DATA_PATH) as f:
        return json.load(f)


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
    ], style={
        "padding": "14px 16px",
        "borderBottom": f"1px solid {COLORS['card_border']}",
        "background": f"{COLORS['primary']}05" if not msg["read"] else "transparent",
        "transition": "background 0.15s",
    })


def _score_product(price_offered):
    """Auto-score a product using the feasibility calculator.

    Uses 2.5x the offered price as estimated sell price, default 1.0 lb weight,
    and conservative estimates for monthly sales and competition.
    """
    sell_price = round(price_offered * 2.5, 2)
    fba_fee = estimate_fba_fee(1.0)
    referral_fee = calc_referral_fee(sell_price)
    result = calc_feasibility(
        price=sell_price,
        cost=price_offered,
        fba_fee=fba_fee,
        referral_fee=referral_fee,
        monthly_sales=200,
    )
    return {
        "sell_price": sell_price,
        "fba_fee": fba_fee,
        "referral_fee": referral_fee,
        "margin": result["margin"],
        "score": result["score"],
        "verdict": result["verdict"],
    }


def _verdict_style(verdict):
    """Return inline style dict for verdict badge."""
    if verdict == "GO":
        color = COLORS["success"]
    elif verdict == "MAYBE":
        color = COLORS["warning"]
    else:
        color = COLORS["danger"]
    return {
        "color": color,
        "fontWeight": "700",
        "background": f"{color}20",
        "padding": "2px 10px",
        "borderRadius": "10px",
        "fontSize": "0.75rem",
        "display": "inline-block",
    }


def _build_products_table(messages):
    """Extract all products from messages into a flat table with auto-scoring."""
    rows = []
    for msg in messages:
        for p in msg.get("products", []):
            price_offered = p["price_offered"]
            scoring = _score_product(price_offered)
            rows.append({
                "product": p["name"],
                "price": f"${price_offered:.2f}",
                "moq": p["moq"],
                "lead_time": p["lead_time"],
                "supplier": p["supplier"],
                "source": msg["source"].title(),
                "from": msg["from"],
                "date": msg["date"][:10],
                "est_sell": f"${scoring['sell_price']:.2f}",
                "fba_fee": f"${scoring['fba_fee']:.2f}",
                "referral_fee": f"${scoring['referral_fee']:.2f}",
                "margin": scoring["margin"],
                "score": scoring["score"],
                "verdict": scoring["verdict"],
                "status": "New",
            })
        # Also include products found by image scanning
        for r in msg.get("scan_results", []):
            if r.get("is_product") and not r.get("skipped") and r.get("product_name"):
                rows.append({
                    "product": r["product_name"],
                    "price": "—",
                    "moq": "—",
                    "lead_time": "—",
                    "supplier": msg["from"],
                    "source": f"{msg['source'].title()} (scan)",
                    "from": msg["from"],
                    "date": msg["date"][:10],
                    "est_sell": "—",
                    "fba_fee": "—",
                    "referral_fee": "—",
                    "margin": 0,
                    "score": 0,
                    "verdict": "—",
                    "status": "Scanned",
                })

    # Sort by feasibility score descending (best opportunities first)
    rows.sort(key=lambda r: r["score"], reverse=True)

    return rows


def _build_products_html_table(rows):
    """Build a styled HTML table for scored products (instead of dash DataTable)."""
    headers = [
        "Product", "Price", "Est. Sell Price", "FBA Fee", "Referral Fee",
        "Est. Margin %", "Score", "Verdict",
        "MOQ", "Lead Time", "Supplier", "Source", "From", "Date", "Status",
    ]

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
        margin_val = row["margin"]
        if isinstance(margin_val, (int, float)) and margin_val != 0:
            if margin_val > 25:
                margin_color = COLORS["success"]
            elif margin_val > 15:
                margin_color = COLORS["warning"]
            else:
                margin_color = COLORS["danger"]
            margin_cell = html.Td(
                f"{margin_val:.1f}%",
                style={**cell_style, "color": margin_color, "fontWeight": "600"},
            )
        else:
            margin_cell = html.Td("—", style=cell_style)

        score_val = row["score"]
        if isinstance(score_val, (int, float)) and score_val != 0:
            if score_val >= 75:
                score_color = COLORS["success"]
            elif score_val >= 50:
                score_color = COLORS["warning"]
            else:
                score_color = COLORS["danger"]
            score_cell = html.Td(
                str(score_val),
                style={**cell_style, "color": score_color, "fontWeight": "700"},
            )
        else:
            score_cell = html.Td("—", style=cell_style)

        verdict_val = row["verdict"]
        if verdict_val in ("GO", "MAYBE", "NO GO"):
            verdict_cell = html.Td(
                html.Span(verdict_val, style=_verdict_style(verdict_val)),
                style=cell_style,
            )
        else:
            verdict_cell = html.Td("—", style=cell_style)

        tr = html.Tr([
            html.Td(row["product"], style=cell_style),
            html.Td(row["price"], style=cell_style),
            html.Td(row["est_sell"], style=cell_style),
            html.Td(row["fba_fee"], style=cell_style),
            html.Td(row["referral_fee"], style=cell_style),
            margin_cell,
            score_cell,
            verdict_cell,
            html.Td(str(row["moq"]), style=cell_style),
            html.Td(str(row["lead_time"]), style=cell_style),
            html.Td(row["supplier"], style=cell_style),
            html.Td(row["source"], style=cell_style),
            html.Td(row["from"], style=cell_style),
            html.Td(row["date"], style=cell_style),
            html.Td(row["status"], style=cell_style),
        ])
        tbody_rows.append(tr)

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


def _build_kpi_row(rows):
    """Build KPI summary row above the products table."""
    # Only count rows with actual scores (not scanned-only rows with score 0 and verdict "—")
    scored_rows = [r for r in rows if isinstance(r["score"], (int, float)) and r["verdict"] in ("GO", "MAYBE", "NO GO")]

    total_products = len(rows)
    go_count = sum(1 for r in scored_rows if r["verdict"] == "GO")

    if scored_rows:
        avg_margin = sum(r["margin"] for r in scored_rows) / len(scored_rows)
    else:
        avg_margin = 0.0

    best_name = scored_rows[0]["product"] if scored_rows else "—"

    # Avg margin color
    if avg_margin > 25:
        margin_color = COLORS["success"]
    elif avg_margin > 15:
        margin_color = COLORS["warning"]
    else:
        margin_color = COLORS["danger"]

    kpi_style = {
        "display": "flex",
        "gap": "16px",
        "marginBottom": "16px",
        "flexWrap": "wrap",
    }

    def _kpi_card(label, value, color):
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
        _kpi_card("Total Products", str(total_products), COLORS["text"]),
        _kpi_card("GO Products", str(go_count), COLORS["success"]),
        _kpi_card("Avg Margin", f"{avg_margin:.1f}%", margin_color),
        _kpi_card("Best Opportunity", best_name, COLORS["primary"]),
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
    kpi_row = _build_kpi_row(rows)
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
            html.P("Ingested emails and WhatsApp messages with product offers"),
        ], className="page-header"),

        # Auto-scan pipeline banner
        html.Div([
            html.Div([
                html.Div([
                    html.I(className="bi bi-camera-fill",
                           style={"fontSize": "1.3rem", "color": COLORS["purple"]}),
                ], style={"flexShrink": "0"}),
                html.Div([
                    html.Span("Auto Image Scanning Pipeline ",
                              style={"color": COLORS["text"], "fontWeight": "600"}),
                    html.Span("— Product images attached to emails and WhatsApp messages are "
                              "automatically detected and scanned by Claude AI. Non-product images "
                              "(logos, signatures, banners) are filtered out. Extracted product data "
                              "appears in the table below.",
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
            _stat_mini("Products Found", str(total_products), "bi-box-seam", COLORS["success"]),
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
                info_card(f"Extracted Product Offers ({len(rows)})",
                          html.Div([
                              html.Div([
                                  html.I(className="bi bi-info-circle me-2",
                                         style={"color": COLORS["info"]}),
                                  html.Span("Products from message text + AI image scans. "
                                            "Auto-scored using the feasibility calculator. "
                                            "Sorted by feasibility score (best first).",
                                            style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
                              ], style={
                                  "background": f"{COLORS['info']}10", "padding": "10px 14px",
                                  "borderRadius": "8px", "marginBottom": "16px",
                              }),
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
        # Scan all unscanned messages
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
        # Scan single message
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

    # Rebuild message feed and products table with scoring
    messages = _load_inbox().get("messages", [])
    message_cards = [_message_card(m) for m in messages]
    rows = _build_products_table(messages)
    kpi_row = _build_kpi_row(rows)
    products_html = _build_products_html_table(rows)

    return status, message_cards, [kpi_row, products_html]
