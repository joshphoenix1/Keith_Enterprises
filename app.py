import json
import logging
import dash
from datetime import datetime
from dash import html, dcc, callback, Input, Output
from flask import request, jsonify, Response as FlaskResponse
from config import COLORS, APP_NAME, APP_PORT
from components.sidebar import create_sidebar

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")

# Dashboard credentials — change these
DASH_USER = "keith"
DASH_PASS = "enterprises2026"

app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    title=APP_NAME,
    external_stylesheets=[
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
    ],
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
    ],
)

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    create_sidebar(),
    html.Div(id="page-content", className="main-content"),
], style={"backgroundColor": COLORS["bg"], "minHeight": "100vh"})


# ── Auth: protect dashboard, allow public /api/ routes ──

PUBLIC_PREFIXES = ("/api/",)


def _check_auth():
    """Check if the request has valid basic auth credentials."""
    auth = request.authorization
    return auth and auth.username == DASH_USER and auth.password == DASH_PASS


@app.server.before_request
def _require_auth():
    """Basic auth on all dashboard routes. /api/ routes are public (buyer-facing)."""
    path = request.path

    # Public routes — buyer response pages, packing slips, etc.
    if any(path.startswith(p) for p in PUBLIC_PREFIXES):
        return None

    # Everything else requires auth (dashboard pages, Dash internals, static assets)
    # Browser caches basic auth per domain so this only prompts once per session
    if _check_auth():
        return None

    return FlaskResponse(
        "Login required.", 401,
        {"WWW-Authenticate": 'Basic realm="Keith Enterprises"'},
    )


@callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname):
    if pathname == "/" or pathname is None:
        from pages.home import layout
        return layout()
    elif pathname == "/inbox":
        from pages.inbox import layout
        return layout()
    elif pathname == "/scanner":
        from pages.scanner import layout
        return layout()
    elif pathname == "/offers":
        from pages.offers import layout
        return layout()
    elif pathname == "/orders":
        from pages.orders import layout
        return layout()
    elif pathname == "/buyers":
        from pages.buyers import layout
        return layout()
    elif pathname == "/accounts":
        from pages.accounts import layout
        return layout()
    elif pathname == "/health":
        from pages.health import layout
        return layout()
    else:
        return html.Div([
            html.H2("404 — Page Not Found"),
            html.P("The page you're looking for doesn't exist."),
        ], className="page-header")


# Import page modules to register their callbacks
import pages.offers
import pages.orders
import pages.buyers
import pages.accounts
import pages.inbox
import pages.scanner
import pages.health


# ── WhatsApp Webhook (Green API) ──
# Green API sends POST requests for incoming messages

server = app.server


@server.route("/api/whatsapp/webhook", methods=["POST"])
def whatsapp_webhook_receive():
    """Handle incoming WhatsApp messages from Green API."""
    from utils.whatsapp import process_webhook_payload, trigger_auto_process
    import os

    wa_logger = logging.getLogger("keith.whatsapp.webhook")

    # Check if WhatsApp is enabled
    accounts_path = os.path.join(os.path.dirname(__file__), "data", "accounts.json")
    auto_process = True
    try:
        with open(accounts_path) as f:
            accounts = json.load(f)
        wa_config = accounts.get("whatsapp", {})
        if not wa_config.get("enabled"):
            return "OK", 200  # Silently accept but don't process
        auto_process = wa_config.get("auto_process_images", True)
    except Exception:
        pass

    # Process the payload
    try:
        payload = request.get_json()
        if not payload:
            return "OK", 200

        processed = process_webhook_payload(payload)

        # Auto-process with Claude AI if enabled (images + URLs)
        if auto_process and processed:
            import threading
            import re
            msg_ids = []
            for m in processed:
                has_images = any(a.get("type") == "image" for a in m.get("attachments", []))
                has_urls = bool(re.search(r'https?://', m.get("body", "")))
                if has_images or has_urls:
                    msg_ids.append(m["id"])
            if msg_ids:
                t = threading.Thread(target=trigger_auto_process, args=(msg_ids,), daemon=True)
                t.start()

        wa_logger.info("Processed %d incoming WhatsApp message(s)", len(processed))

    except Exception as e:
        wa_logger.error("Error processing webhook: %s", e)

    return "OK", 200


@server.route("/api/whatsapp/send", methods=["POST"])
def whatsapp_send_message():
    """API endpoint to send a WhatsApp message from the dashboard."""
    from utils.whatsapp import send_message

    data = request.get_json()
    if not data or not data.get("to") or not data.get("message"):
        return jsonify({"error": "Missing 'to' and/or 'message' fields"}), 400

    result = send_message(data["to"], data["message"])
    return jsonify(result), 200 if result.get("success") else 500


# ── Packing Slip ──

@server.route("/api/packing-slip/<order_id>")
def packing_slip(order_id):
    """Printable packing slip or drop-ship instruction sheet.

    Query params:
        mode=dropship  — supplier drop-ship instructions (default: packing slip)
        format=pdf     — download as PDF (default: HTML)
    """
    import os
    from config import COMPANY
    mode = request.args.get("mode", "pack")  # pack or dropship
    fmt = request.args.get("format", "html")  # html or pdf

    orders_path = os.path.join(os.path.dirname(__file__), "data", "orders.json")
    buyers_path = os.path.join(os.path.dirname(__file__), "data", "buyers.json")

    try:
        with open(orders_path) as f:
            orders = json.load(f)
    except Exception:
        return "Orders not found", 404

    order = next((o for o in orders if o.get("id") == order_id), None)
    if not order:
        return "Order not found", 404

    # Load buyer for shipping address
    try:
        with open(buyers_path) as f:
            buyers = json.load(f)
    except Exception:
        buyers = []

    buyer = next((b for b in buyers if b.get("id") == order.get("buyer_id")), None)
    ship_addr = (buyer or {}).get("shipping_address", {}) if buyer else {}

    # Build ship-to address
    ship_to_lines = [order.get("buyer_name", "")]
    if buyer:
        if buyer.get("company"):
            ship_to_lines.insert(0, buyer["company"])
    if ship_addr.get("line1"):
        ship_to_lines.append(ship_addr["line1"])
    if ship_addr.get("line2"):
        ship_to_lines.append(ship_addr["line2"])
    city_state = ""
    if ship_addr.get("city"):
        city_state = ship_addr["city"]
    if ship_addr.get("state"):
        city_state += f", {ship_addr['state']}"
    if ship_addr.get("zip"):
        city_state += f" {ship_addr['zip']}"
    if city_state:
        ship_to_lines.append(city_state)
    if buyer and buyer.get("phone"):
        ship_to_lines.append(f"Phone: {buyer['phone']}")
    if order.get("buyer_email"):
        ship_to_lines.append(order["buyer_email"])

    ship_to_html = "<br>".join(ship_to_lines)

    # Ship-from / return address
    from_lines = [COMPANY["name"]]
    if COMPANY.get("address_line1"):
        from_lines.append(COMPANY["address_line1"])
    if COMPANY.get("address_line2"):
        from_lines.append(COMPANY["address_line2"])
    from_city = ""
    if COMPANY.get("city"):
        from_city = COMPANY["city"]
    if COMPANY.get("state"):
        from_city += f", {COMPANY['state']}"
    if COMPANY.get("zip"):
        from_city += f" {COMPANY['zip']}"
    if from_city:
        from_lines.append(from_city)
    if COMPANY.get("phone"):
        from_lines.append(f"Phone: {COMPANY['phone']}")
    if COMPANY.get("email"):
        from_lines.append(COMPANY["email"])

    from_html = "<br>".join(from_lines)

    # Line items
    items = order.get("items", [])
    total_units = sum(item.get("qty", 0) for item in items)
    item_rows = ""
    for i, item in enumerate(items, 1):
        item_rows += f"""<tr>
            <td style="padding:8px 12px;border-bottom:1px solid #ddd;text-align:center;">{i}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #ddd;">{item.get('product_name','')}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #ddd;font-family:monospace;font-size:12px;">{item.get('upc','')}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #ddd;text-align:center;font-weight:bold;">{item.get('qty',0)}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #ddd;text-align:center;">
                <span style="display:inline-block;width:18px;height:18px;border:2px solid #999;border-radius:3px;"></span>
            </td>
        </tr>"""

    tracking = order.get("tracking_number", "") or "________________"
    carrier = order.get("carrier", "") or "________________"
    ship_date = order.get("shipped_at", "") or datetime.now().strftime("%Y-%m-%d")

    # Mode-specific title and header
    if mode == "dropship":
        doc_title = "Drop-Ship Instructions"
        doc_header = "DROP-SHIP ORDER"
        doc_subtitle = "Supplier Fulfillment Instructions"
    else:
        doc_title = "Packing Slip"
        doc_header = "PACKING SLIP"
        doc_subtitle = "Keith Enterprises"

    # Supplier instructions block (drop-ship only)
    supplier_instructions = ""
    if mode == "dropship":
        supplier_instructions = f"""
        <div style="border:2px solid #c00;border-radius:8px;padding:16px;margin-bottom:24px;background:#fff5f5;">
            <h3 style="margin:0 0 8px;color:#c00;">⚠ SUPPLIER INSTRUCTIONS — PLEASE READ</h3>
            <ol style="margin:8px 0;padding-left:20px;font-size:14px;line-height:1.8;">
                <li><strong>Ship directly to the customer address shown below.</strong></li>
                <li>Do NOT include any invoices, price lists, or promotional material in the package.</li>
                <li>Use the packing slip below as the only document inside the package.</li>
                <li>Ship via the method indicated. If unavailable, use equivalent ground service.</li>
                <li>Email tracking number to <strong>{COMPANY.get('email','')}</strong> once shipped.</li>
                <li>Reference order <strong>{order_id}</strong> in all communications.</li>
            </ol>
        </div>"""

    page = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>{doc_title} — {order_id}</title>
<style>
    @media print {{
        body {{ margin: 0; }}
        .no-print {{ display: none !important; }}
        @page {{ margin: 0.5in; }}
    }}
    body {{ font-family: Arial, Helvetica, sans-serif; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
    table {{ border-collapse: collapse; }}
</style>
</head>
<body>

<div class="no-print" style="text-align:center;margin-bottom:20px;display:flex;gap:12px;justify-content:center;flex-wrap:wrap;">
    <button onclick="window.print()" style="background:#1f6feb;color:#fff;border:none;padding:12px 24px;
        border-radius:6px;font-size:14px;font-weight:600;cursor:pointer;">
        🖨️ Print
    </button>
    <a href="/api/packing-slip/{order_id}?mode={mode}&format=pdf" style="background:#333;color:#fff;
        padding:12px 24px;border-radius:6px;font-size:14px;font-weight:600;text-decoration:none;display:inline-block;">
        📄 Download PDF
    </a>
    <a href="/api/packing-slip/{order_id}?mode={'dropship' if mode != 'dropship' else 'pack'}"
        style="background:#d29922;color:#fff;padding:12px 24px;border-radius:6px;font-size:14px;
        font-weight:600;text-decoration:none;display:inline-block;">
        {'📦 Switch to Packing Slip' if mode == 'dropship' else '🚚 Switch to Drop-Ship Instructions'}
    </a>
</div>

{supplier_instructions}

<!-- Header -->
<div style="display:flex;justify-content:space-between;align-items:flex-start;border-bottom:3px solid #333;padding-bottom:16px;margin-bottom:20px;">
    <div>
        <h1 style="margin:0;font-size:24px;">{doc_header}</h1>
        <p style="margin:4px 0 0;color:#666;">{doc_subtitle}</p>
    </div>
    <div style="text-align:right;">
        <p style="margin:0;"><strong>Order:</strong> {order_id}</p>
        <p style="margin:4px 0;"><strong>Date:</strong> {ship_date}</p>
        <p style="margin:4px 0;"><strong>Items:</strong> {len(items)} ({total_units} units)</p>
    </div>
</div>

<!-- Addresses -->
<div style="display:flex;gap:40px;margin-bottom:24px;">
    <div style="flex:1;border:1px solid #ddd;border-radius:6px;padding:16px;">
        <p style="margin:0 0 8px;font-size:11px;color:#999;text-transform:uppercase;letter-spacing:1px;font-weight:bold;">Ship To</p>
        <p style="margin:0;font-size:14px;line-height:1.6;">{ship_to_html}</p>
    </div>
    <div style="flex:1;border:1px solid #ddd;border-radius:6px;padding:16px;">
        <p style="margin:0 0 8px;font-size:11px;color:#999;text-transform:uppercase;letter-spacing:1px;font-weight:bold;">Ship From / Return Address</p>
        <p style="margin:0;font-size:14px;line-height:1.6;">{from_html}</p>
    </div>
</div>

<!-- Shipping Info -->
<div style="display:flex;gap:20px;margin-bottom:24px;background:#f9f9f9;padding:14px 18px;border-radius:6px;">
    <div style="flex:1;">
        <span style="font-size:12px;color:#666;">Carrier:</span><br>
        <strong>{carrier}</strong>
    </div>
    <div style="flex:1;">
        <span style="font-size:12px;color:#666;">Tracking Number:</span><br>
        <strong>{tracking}</strong>
    </div>
    <div style="flex:1;">
        <span style="font-size:12px;color:#666;">Ship Method:</span><br>
        <strong>{order.get('ship_method', 'Ground')}</strong>
    </div>
    <div style="flex:1;">
        <span style="font-size:12px;color:#666;">Payment Terms:</span><br>
        <strong>{order.get('payment_terms', 'Wire before ship')}</strong>
    </div>
</div>

<!-- Items -->
<table style="width:100%;margin-bottom:20px;">
    <thead>
        <tr style="background:#333;color:#fff;">
            <th style="padding:10px 12px;text-align:center;width:40px;">#</th>
            <th style="padding:10px 12px;text-align:left;">Product Description</th>
            <th style="padding:10px 12px;text-align:left;width:130px;">UPC</th>
            <th style="padding:10px 12px;text-align:center;width:60px;">Qty</th>
            <th style="padding:10px 12px;text-align:center;width:60px;">Verified</th>
        </tr>
    </thead>
    <tbody>
        {item_rows}
    </tbody>
    <tfoot>
        <tr style="background:#f5f5f5;font-weight:bold;">
            <td colspan="3" style="padding:10px 12px;text-align:right;">Total Units:</td>
            <td style="padding:10px 12px;text-align:center;">{total_units}</td>
            <td></td>
        </tr>
    </tfoot>
</table>

<!-- Footer notes -->
<div style="border-top:1px solid #ddd;padding-top:16px;margin-top:20px;">
    <div style="display:flex;gap:40px;">
        <div style="flex:1;">
            <p style="font-size:12px;color:#666;margin:0 0 4px;font-weight:bold;">PACKED BY:</p>
            <div style="border-bottom:1px solid #999;height:30px;"></div>
        </div>
        <div style="flex:1;">
            <p style="font-size:12px;color:#666;margin:0 0 4px;font-weight:bold;">DATE PACKED:</p>
            <div style="border-bottom:1px solid #999;height:30px;"></div>
        </div>
        <div style="flex:1;">
            <p style="font-size:12px;color:#666;margin:0 0 4px;font-weight:bold;">TOTAL BOXES:</p>
            <div style="border-bottom:1px solid #999;height:30px;"></div>
        </div>
    </div>
</div>

<div style="margin-top:24px;padding:14px;background:#f9f9f9;border-radius:6px;font-size:12px;color:#666;">
    <p style="margin:0 0 4px;font-weight:bold;">Notes:</p>
    <p style="margin:0;">{order.get('notes', '') or 'Please inspect all items upon receipt. Report any damage or discrepancies within 48 hours of delivery. Contact us at ' + COMPANY.get('email', '') + ' for any questions regarding this shipment.'}</p>
</div>

<div style="text-align:center;margin-top:24px;font-size:11px;color:#999;">
    <p>Thank you for your business! — Keith Enterprises</p>
</div>

</body></html>"""

    if fmt == "pdf":
        try:
            import weasyprint
            from flask import Response
            pdf = weasyprint.HTML(string=page).write_pdf()
            return Response(
                pdf,
                mimetype="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={order_id}-{mode}.pdf"},
            )
        except Exception as e:
            return f"PDF generation error: {e}", 500

    return page


# ── USPS Address Verification API ──

@server.route("/api/verify-address", methods=["POST"])
def verify_address_api():
    """AJAX endpoint for USPS address verification."""
    from utils.usps import verify_address
    data = request.get_json()
    if not data:
        return jsonify({"verified": False, "error": "No data"}), 400
    result = verify_address(
        line1=data.get("line1", ""),
        line2=data.get("line2", ""),
        city=data.get("city", ""),
        state=data.get("state", ""),
        zip5=data.get("zip", ""),
    )
    return jsonify(result)


# ── Buyer Offer Response Page ──

@server.route("/api/buyer/respond/<token>", methods=["GET", "POST"])
def buyer_respond(token):
    """Web page for buyers to accept offers, specify quantities, and place orders."""
    import os
    import threading
    from utils.orders import get_available_qty_bulk, create_order

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    offers_path = os.path.join(data_dir, "offers.json")
    batches_path = os.path.join(data_dir, "offer_batches.json")

    try:
        with open(batches_path) as f:
            batches = json.load(f)
    except Exception:
        batches = {}

    batch = batches.get(token)
    if not batch:
        return "Invalid or expired link.", 404

    buyer_name = batch.get("buyer_name", "")
    buyer_email = batch.get("buyer_email", "")
    buyer_id = batch.get("buyer_id", 0)
    offer_ids = batch.get("offer_ids", [])

    try:
        with open(offers_path) as f:
            all_offers = json.load(f)
    except Exception:
        all_offers = []

    offers = [o for o in all_offers if o.get("id") in offer_ids]

    # Dynamic availability
    avail_map = get_available_qty_bulk(offer_ids)


    order_created = None
    submitted = False

    if request.method == "POST":
        form = request.form
        accepted_items = []

        for o in offers:
            oid = str(o["id"])
            decision = form.get(f"decision_{oid}", "")
            qty_str = form.get(f"qty_{oid}", "0")
            qty = int(qty_str) if qty_str.isdigit() else 0

            if decision == "accept" and qty > 0:
                # Cap to available
                available = avail_map.get(o["id"], 0)
                qty = min(qty, available)
                if qty > 0:
                    accepted_items.append({
                        "offer_id": o["id"],
                        "product_name": o.get("product_name", ""),
                        "upc": o.get("upc", ""),
                        "unit_cost": o.get("wholesale_price") or o.get("per_unit_cost") or 0,
                        "qty": qty,
                    })

        if accepted_items:
            # Create the order
            order_created = create_order(
                buyer_id=buyer_id,
                buyer_name=buyer_name,
                buyer_email=buyer_email,
                accepted_items=accepted_items,
            )

            # Update offer statuses
            accepted_offer_ids = {item["offer_id"] for item in accepted_items}
            for o in all_offers:
                if o.get("id") in accepted_offer_ids:
                    o["status"] = "accepted"
            with open(offers_path, "w") as f:
                json.dump(all_offers, f, indent=2)

            # Send notifications in background
            def _notify():
                try:
                    from utils.notifications import notify_team_email, send_buyer_confirmation
                    notify_team_email(order_created)
                    send_buyer_confirmation(order_created, order_created.get("buyer_email", ""))
                except Exception as e:
                    logging.getLogger("keith.orders").error("Notification error: %s", e)

            threading.Thread(target=_notify, daemon=True).start()

            # Refresh availability after order
            avail_map = get_available_qty_bulk(offer_ids)

        submitted = True

    # Build HTML rows
    rows_html = ""
    for o in offers:
        mp = o.get("marketplace_data") or {}
        oid = str(o["id"])
        available = avail_map.get(o["id"], 0)
        upc = o.get("upc", "")

        sa = o.get('sa_data') or {}

        # Amazon link — prefer SA product URL (direct ASIN link), fall back to search
        amazon_url = sa.get('product_url', '')
        if not amazon_url and upc:
            amazon_url = f"https://www.amazon.com/s?k={upc}"
        elif not amazon_url and o.get("product_name"):
            import urllib.parse
            amazon_url = f"https://www.amazon.com/s?k={urllib.parse.quote(o['product_name'])}"

        product_cell = o.get('product_name', '')
        if amazon_url:
            product_cell = f'<a href="{amazon_url}" target="_blank" style="color:#58a6ff;text-decoration:none;">{product_cell}</a>'

        # Use SA Buy Box price if available, fall back to scraped
        buy_box = sa.get('buy_box_price') or mp.get('amazon_price') or 0
        buy_box_display = f"${buy_box:.2f}" if buy_box else "—"

        # Monthly sales from SA
        mo_sales = sa.get('estimated_monthly_sales') or 0
        mo_sales_display = f"{mo_sales:,}" if mo_sales else "—"

        # Profit from SA
        profit = sa.get('profit_per_unit') or sa.get('buyer_profit') or 0
        profit_display = f"${profit:.2f}" if profit else "—"
        profit_color = "#3fb950" if profit > 0 else "#f85149" if profit < 0 else "#8b949e"

        # FBA sellers
        fba_sellers = sa.get('fba_sellers', '')
        fba_display = str(fba_sellers) if fba_sellers != '' else "—"

        avail_color = "#3fb950" if available > 50 else "#d29922" if available > 0 else "#f85149"

        rows_html += f'''<tr style="border-bottom:1px solid #30363d;">
            <td style="padding:10px;color:#e6edf3;">{product_cell}</td>
            <td style="padding:10px;color:#8b949e;font-size:0.8rem;">{o.get('category','')}</td>
            <td style="padding:10px;color:#e6edf3;">${(o.get('wholesale_price') or o.get('per_unit_cost') or 0):.2f}</td>
            <td style="padding:10px;color:#3fb950;">{buy_box_display}</td>
            <td style="padding:10px;color:{profit_color};font-weight:600;">{profit_display}</td>
            <td style="padding:10px;color:#58a6ff;">{(o.get('margin_pct') or 0):.0f}%</td>
            <td style="padding:10px;color:#8b949e;">{mo_sales_display}</td>
            <td style="padding:10px;color:#8b949e;">{fba_display}</td>
            <td style="padding:10px;color:{avail_color};font-weight:600;">{available}</td>
            <td style="padding:10px;text-align:center;">
                <label style="color:#3fb950;margin-right:12px;cursor:pointer;">
                    <input type="radio" name="decision_{oid}" value="accept"> Accept
                </label>
                <label style="color:#8b949e;cursor:pointer;">
                    <input type="radio" name="decision_{oid}" value="" checked> Skip
                </label>
            </td>
            <td style="padding:10px;">
                <input type="number" name="qty_{oid}" min="0" max="{available}" placeholder="0"
                    class="qty-input" data-oid="{oid}" data-max="{available}"
                    data-price="{(o.get('wholesale_price') or o.get('per_unit_cost') or 0):.2f}"
                    style="width:80px;background:#0d1117;border:1px solid #30363d;color:#e6edf3;
                    border-radius:4px;padding:4px 6px;text-align:center;">
            </td>
        </tr>'''

    # Success / order confirmation message
    success_msg = ""
    if submitted and order_created:
        items = order_created.get("items", [])
        order_rows = ""
        for item in items:
            order_rows += f'''<tr>
                <td style="padding:6px 10px;">{item["product_name"]}</td>
                <td style="padding:6px 10px;text-align:center;">{item["qty"]}</td>
                <td style="padding:6px 10px;text-align:right;">${item["unit_cost"]:.2f}</td>
                <td style="padding:6px 10px;text-align:right;">${item["line_total"]:.2f}</td>
            </tr>'''

        success_msg = f'''<div style="background:#3fb95015;border:1px solid #3fb95040;padding:20px;
            border-radius:10px;margin-bottom:24px;">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">
                <span style="font-size:1.5rem;">✅</span>
                <div>
                    <h3 style="margin:0;color:#3fb950;">Order Placed — {order_created["id"]}</h3>
                    <p style="margin:2px 0 0;color:#8b949e;font-size:0.85rem;">
                        Confirmation email sent to {buyer_email}</p>
                </div>
            </div>
            <table style="width:100%;border-collapse:collapse;background:#1c2128;border-radius:6px;overflow:hidden;">
                <thead><tr style="background:#161b22;">
                    <th style="padding:8px 10px;text-align:left;color:#8b949e;font-size:0.8rem;">Product</th>
                    <th style="padding:8px 10px;text-align:center;color:#8b949e;font-size:0.8rem;">Qty</th>
                    <th style="padding:8px 10px;text-align:right;color:#8b949e;font-size:0.8rem;">Unit</th>
                    <th style="padding:8px 10px;text-align:right;color:#8b949e;font-size:0.8rem;">Total</th>
                </tr></thead>
                <tbody>{order_rows}</tbody>
                <tfoot><tr style="background:#161b22;">
                    <td colspan="3" style="padding:10px;text-align:right;color:#e6edf3;font-weight:600;">Order Total:</td>
                    <td style="padding:10px;text-align:right;color:#3fb950;font-weight:700;font-size:1.1rem;">
                        ${order_created["subtotal"]:,.2f}</td>
                </tr></tfoot>
            </table>
            <div style="margin-top:14px;padding:12px;background:#58a6ff15;border-radius:6px;">
                <p style="margin:0;color:#58a6ff;font-size:0.85rem;">
                    <strong>Next steps:</strong> We will be in contact to arrange payment &amp; shipping.</p>
            </div>
        </div>'''
    elif submitted and not order_created:
        success_msg = '''<div style="background:#d2992215;border:1px solid #d2992240;padding:14px 18px;
            border-radius:8px;margin-bottom:20px;color:#d29922;">
            No items were accepted. Select products and enter quantities to place an order.</div>'''

    html_page = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Keith Enterprises — Offer Review</title></head>
<body style="background:#0f1117;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;margin:0;padding:20px;">
<div style="max-width:1200px;margin:0 auto;">
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:24px;">
        <div style="width:48px;height:48px;border-radius:12px;background:#58a6ff15;display:flex;
            align-items:center;justify-content:center;font-size:1.4rem;">📦</div>
        <div>
            <h2 style="margin:0;color:#e6edf3;">Offer Review — {buyer_name}</h2>
            <p style="margin:4px 0 0;color:#8b949e;font-size:0.9rem;">
                Click a product name to view on Amazon. Enter a quantity to accept.</p>
        </div>
    </div>
    {success_msg}
    <form method="POST">
    <div style="overflow-x:auto;border:1px solid #30363d;border-radius:8px;">
    <table style="width:100%;border-collapse:collapse;background:#1c2128;">
        <thead><tr style="background:#161b22;">
            <th style="padding:10px;text-align:left;color:#8b949e;font-size:0.8rem;">Product</th>
            <th style="padding:10px;text-align:left;color:#8b949e;font-size:0.8rem;">Category</th>
            <th style="padding:10px;text-align:left;color:#8b949e;font-size:0.8rem;">Your Price</th>
            <th style="padding:10px;text-align:left;color:#8b949e;font-size:0.8rem;">Amazon Price</th>
            <th style="padding:10px;text-align:left;color:#8b949e;font-size:0.8rem;">Est. Profit</th>
            <th style="padding:10px;text-align:left;color:#8b949e;font-size:0.8rem;">Margin</th>
            <th style="padding:10px;text-align:left;color:#8b949e;font-size:0.8rem;">Mo. Sales</th>
            <th style="padding:10px;text-align:left;color:#8b949e;font-size:0.8rem;">FBA</th>
            <th style="padding:10px;text-align:left;color:#8b949e;font-size:0.8rem;">Available</th>
            <th style="padding:10px;text-align:center;color:#8b949e;font-size:0.8rem;">Decision</th>
            <th style="padding:10px;text-align:left;color:#8b949e;font-size:0.8rem;">Your Qty</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
    </div>
    <p style="color:#8b949e;font-size:0.75rem;margin:10px 0 0;">Est. Profit is calculated per unit after Amazon referral and FBA fulfillment fees.</p>
    <div id="order-summary" style="position:sticky;bottom:0;background:#161b22;border:1px solid #30363d;
        border-radius:8px 8px 0 0;padding:14px 20px;margin-top:20px;display:flex;align-items:center;
        justify-content:space-between;box-shadow:0 -4px 12px rgba(0,0,0,0.4);">
        <div style="display:flex;gap:24px;align-items:center;">
            <span style="color:#8b949e;font-size:0.85rem;"><span id="item-count" style="color:#e6edf3;font-weight:600;">0</span> items</span>
            <span style="color:#8b949e;font-size:0.85rem;"><span id="unit-count" style="color:#e6edf3;font-weight:600;">0</span> units</span>
            <span style="color:#8b949e;font-size:0.85rem;">Total: <span id="rolling-total" style="color:#3fb950;font-weight:700;font-size:1.1rem;">$0.00</span></span>
        </div>
        <button type="submit" style="background:#1f6feb;color:#fff;border:none;padding:10px 28px;
            border-radius:6px;font-size:0.95rem;font-weight:600;cursor:pointer;">
            Submit Order
        </button>
    </div>
    </form>
</div>
''' + '''<script>
function updateTotal() {
    var total = 0, items = 0, units = 0;
    document.querySelectorAll('.qty-input').forEach(function(input) {
        var oid = input.dataset.oid;
        var qty = parseInt(input.value) || 0;
        var accept = document.querySelector('input[name="decision_' + oid + '"][value="accept"]');
        if (accept && accept.checked && qty > 0) {
            var price = parseFloat(input.dataset.price) || 0;
            total += price * qty;
            units += qty;
            items++;
        }
    });
    document.getElementById('rolling-total').textContent = '$' + total.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    document.getElementById('item-count').textContent = items;
    document.getElementById('unit-count').textContent = units.toLocaleString();
}

document.querySelectorAll('.qty-input').forEach(function(input) {
    input.addEventListener('input', function() {
        var oid = this.dataset.oid;
        var max = parseInt(this.dataset.max) || 0;
        var val = parseInt(this.value) || 0;
        if (val > max) { this.value = max; val = max; }
        if (val < 0) { this.value = 0; val = 0; }
        if (val > 0) {
            var accept = document.querySelector('input[name="decision_' + oid + '"][value="accept"]');
            if (accept) accept.checked = true;
        }
        updateTotal();
    });
});

document.querySelectorAll('input[type="radio"]').forEach(function(radio) {
    radio.addEventListener('change', updateTotal);
});
</script>
</body></html>'''

    return html_page


if __name__ == "__main__":
    import os
    from utils.healthcheck import HealthChecker
    from utils.email_client import EmailPoller
    from utils.seller_assistant import EnrichmentPoller
    # Start background services (debug=False so no reloader — always start)
    if True:
        checker = HealthChecker(app=app, interval=60)
        app.server.health_checker = checker
        checker.start()

        email_poller = EmailPoller(interval=120)
        app.server.email_poller = email_poller
        email_poller.start()

        sa_poller = EnrichmentPoller(interval=300, batch_size=50)
        app.server.sa_poller = sa_poller
        sa_poller.start()
    app.run(debug=False, host="0.0.0.0", port=APP_PORT)
