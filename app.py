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

        # Auto-process images with Claude AI if enabled
        if auto_process and processed:
            import threading
            msg_ids = [m["id"] for m in processed
                       if any(a.get("type") == "image" for a in m.get("attachments", []))]
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


if __name__ == "__main__":
    import os
    from utils.healthcheck import HealthChecker
    # Only start health checker in the reloader's child process (or non-debug mode)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not True:
        checker = HealthChecker(app=app, interval=60)
        app.server.health_checker = checker
        checker.start()
    app.run(debug=True, host="0.0.0.0", port=APP_PORT,
            dev_tools_ui=False, dev_tools_props_check=False)
