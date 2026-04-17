import json
import logging
import dash
from dash import html, dcc, callback, Input, Output
from flask import request, jsonify
from config import COLORS, APP_NAME, APP_PORT
from components.sidebar import create_sidebar

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")

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
                        "unit_cost": o.get("per_unit_cost", 0) or 0,
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
                    send_buyer_confirmation(order_created)
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

        # Amazon link
        amazon_url = ""
        if upc:
            amazon_url = f"https://www.amazon.com/s?k={upc}"
        elif o.get("product_name"):
            import urllib.parse
            amazon_url = f"https://www.amazon.com/s?k={urllib.parse.quote(o['product_name'])}"

        product_cell = o.get('product_name', '')
        if amazon_url:
            product_cell = f'<a href="{amazon_url}" target="_blank" style="color:#58a6ff;text-decoration:none;">{product_cell}</a>'

        amz_price = mp.get('amazon_price', 0)
        amz_display = f"${amz_price:.2f}" if amz_price else "—"

        avail_color = "#3fb950" if available > 50 else "#d29922" if available > 0 else "#f85149"

        rows_html += f'''<tr style="border-bottom:1px solid #30363d;">
            <td style="padding:10px;color:#e6edf3;">{product_cell}</td>
            <td style="padding:10px;color:#8b949e;">{o.get('category','')}</td>
            <td style="padding:10px;color:#e6edf3;">${o.get('per_unit_cost',0):.2f}</td>
            <td style="padding:10px;color:#3fb950;">{amz_display}</td>
            <td style="padding:10px;color:#58a6ff;">{o.get('margin_pct',0):.0f}%</td>
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
                    <strong>Next steps:</strong> We'll confirm availability within 24 hours and send payment instructions.
                    Quantities are held for 48 hours.</p>
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
            <th style="padding:10px;text-align:left;color:#8b949e;font-size:0.8rem;">Unit Cost</th>
            <th style="padding:10px;text-align:left;color:#8b949e;font-size:0.8rem;">Amazon</th>
            <th style="padding:10px;text-align:left;color:#8b949e;font-size:0.8rem;">Margin</th>
            <th style="padding:10px;text-align:left;color:#8b949e;font-size:0.8rem;">Available</th>
            <th style="padding:10px;text-align:center;color:#8b949e;font-size:0.8rem;">Decision</th>
            <th style="padding:10px;text-align:left;color:#8b949e;font-size:0.8rem;">Your Qty</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
    </div>
    <div style="margin-top:20px;text-align:right;">
        <button type="submit" style="background:#1f6feb;color:#fff;border:none;padding:12px 32px;
            border-radius:6px;font-size:1rem;font-weight:600;cursor:pointer;">
            Place Order
        </button>
    </div>
    </form>
</div>
''' + '''<script>
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
    });
});
</script>
</body></html>'''

    return html_page


if __name__ == "__main__":
    import os
    from utils.healthcheck import HealthChecker
    from utils.email_client import EmailPoller
    # Only start health checker in the reloader's child process (or non-debug mode)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not True:
        checker = HealthChecker(app=app, interval=60)
        app.server.health_checker = checker
        checker.start()

        email_poller = EmailPoller(interval=120)
        app.server.email_poller = email_poller
        email_poller.start()
    app.run(debug=False, host="0.0.0.0", port=APP_PORT)
