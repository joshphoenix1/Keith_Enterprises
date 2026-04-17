"""Order notification utilities — email and WhatsApp alerts for orders.

Sends HTML emails via Gmail SMTP and WhatsApp messages via the Baileys bridge.
Uses credentials from data/accounts.json.
"""

import json
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
ACCOUNTS_PATH = os.path.join(DATA_DIR, "accounts.json")

logger = logging.getLogger("keith.notifications")


def _load_email_config():
    """Load email SMTP config from accounts.json."""
    try:
        with open(ACCOUNTS_PATH) as f:
            accounts = json.load(f)
        return accounts.get("email", {})
    except Exception:
        return {}


def _smtp_send(to_address, subject, html_body):
    """Send an HTML email via SMTP using stored Gmail credentials.

    Returns dict with success status.
    """
    config = _load_email_config()
    from_address = config.get("email_address", "")
    password = config.get("password", "")
    smtp_server = config.get("smtp_server", "") or "smtp.gmail.com"
    smtp_port = config.get("smtp_port", 587)
    use_tls = config.get("use_tls", True)

    if not from_address or not password:
        logger.error("Email credentials not configured in accounts.json")
        return {"success": False, "error": "Email credentials not configured"}

    msg = MIMEMultipart("alternative")
    msg["From"] = f"Keith Enterprises <{from_address}>"
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        if use_tls:
            server.starttls()
        server.login(from_address, password)
        server.sendmail(from_address, to_address, msg.as_string())
        server.quit()
        logger.info("Email sent to %s: %s", to_address, subject)
        return {"success": True}
    except Exception as e:
        logger.error("SMTP send failed to %s: %s", to_address, e)
        return {"success": False, "error": str(e)}


# ── Team Notifications ──

def notify_team_email(order):
    """Send an HTML email to the team about a new order.

    Self-notifies using the configured Gmail address.
    """
    config = _load_email_config()
    team_email = config.get("email_address", "")
    if not team_email:
        return {"success": False, "error": "No team email configured"}

    order_id = order.get("id", "N/A")
    buyer = order.get("buyer_name", "Unknown")
    item_count = len(order.get("items", []))
    subtotal = order.get("subtotal", 0)

    subject = f"New Order {order_id} — {buyer} (${subtotal:,.2f})"

    items_rows = ""
    for item in order.get("items", []):
        items_rows += (
            f"<tr>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #eee;'>{item.get('product_name', '—')}</td>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #eee;text-align:center;'>{item.get('qty', 0)}</td>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #eee;text-align:right;'>${item.get('unit_cost', 0):,.2f}</td>"
            f"<td style='padding:6px 12px;border-bottom:1px solid #eee;text-align:right;'>${item.get('line_total', 0):,.2f}</td>"
            f"</tr>"
        )

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
        <div style="background:#1a1a2e;color:#fff;padding:20px 24px;border-radius:8px 8px 0 0;">
            <h2 style="margin:0;">New Order Received</h2>
        </div>
        <div style="background:#fff;padding:24px;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 8px 8px;">
            <table style="width:100%;margin-bottom:16px;">
                <tr><td style="color:#666;padding:4px 0;">Order ID</td><td style="font-weight:bold;">{order_id}</td></tr>
                <tr><td style="color:#666;padding:4px 0;">Buyer</td><td style="font-weight:bold;">{buyer}</td></tr>
                <tr><td style="color:#666;padding:4px 0;">Items</td><td>{item_count}</td></tr>
                <tr><td style="color:#666;padding:4px 0;">Total</td><td style="font-weight:bold;font-size:18px;color:#2d6a4f;">${subtotal:,.2f}</td></tr>
                <tr><td style="color:#666;padding:4px 0;">Payment Terms</td><td>{order.get('payment_terms', '—')}</td></tr>
                <tr><td style="color:#666;padding:4px 0;">Created</td><td>{order.get('created_at', '—')}</td></tr>
            </table>

            <h3 style="margin:16px 0 8px;border-bottom:2px solid #1a1a2e;padding-bottom:4px;">Line Items</h3>
            <table style="width:100%;border-collapse:collapse;">
                <thead>
                    <tr style="background:#f5f5f5;">
                        <th style="padding:8px 12px;text-align:left;">Product</th>
                        <th style="padding:8px 12px;text-align:center;">Qty</th>
                        <th style="padding:8px 12px;text-align:right;">Unit Cost</th>
                        <th style="padding:8px 12px;text-align:right;">Line Total</th>
                    </tr>
                </thead>
                <tbody>
                    {items_rows}
                </tbody>
                <tfoot>
                    <tr style="background:#f5f5f5;font-weight:bold;">
                        <td colspan="3" style="padding:8px 12px;text-align:right;">Subtotal</td>
                        <td style="padding:8px 12px;text-align:right;color:#2d6a4f;">${subtotal:,.2f}</td>
                    </tr>
                </tfoot>
            </table>

            <p style="color:#888;font-size:12px;margin-top:20px;">
                Payment: {order.get('payment_status', 'unpaid')} | Shipping: {order.get('shipping_status', 'not_shipped')}
            </p>
        </div>
    </div>
    """

    return _smtp_send(team_email, subject, html)


def notify_team_whatsapp(order, phone_number=None):
    """Send a WhatsApp message to the team with an order summary.

    Uses the existing WhatsApp bridge via utils.whatsapp.send_message.
    If phone_number is not provided, uses the number from whatsapp config.
    """
    from utils.whatsapp import send_message, _load_wa_config

    if not phone_number:
        wa_config = _load_wa_config()
        phone_number = wa_config.get("phone_number", "")
    if not phone_number:
        logger.error("No WhatsApp phone number provided or configured")
        return {"success": False, "error": "No phone number configured"}

    order_id = order.get("id", "N/A")
    buyer = order.get("buyer_name", "Unknown")
    item_count = len(order.get("items", []))
    subtotal = order.get("subtotal", 0)

    text = (
        f"NEW ORDER {order_id}\n"
        f"Buyer: {buyer}\n"
        f"Items: {item_count} | Total: ${subtotal:,.2f}\n"
        f"Payment: {order.get('payment_terms', '—')}\n"
        f"Status: {order.get('payment_status', 'unpaid')}"
    )

    return send_message(phone_number, text)


# ── Buyer-Facing Emails ──

def send_buyer_confirmation(order, buyer_email):
    """Send an HTML order confirmation email to the buyer.

    Includes a line-items table and next-steps messaging.
    """
    order_id = order.get("id", "N/A")
    buyer = order.get("buyer_name", "")
    subtotal = order.get("subtotal", 0)

    subject = f"Order Confirmation — {order_id}"

    items_rows = ""
    for item in order.get("items", []):
        items_rows += (
            f"<tr>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #eee;'>{item.get('product_name', '—')}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #eee;text-align:center;'>{item.get('qty', 0)}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #eee;text-align:right;'>${item.get('unit_cost', 0):,.2f}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #eee;text-align:right;'>${item.get('line_total', 0):,.2f}</td>"
            f"</tr>"
        )

    # Shipping address
    ship_addr = order.get("shipping_address", {})
    addr_lines = []
    if ship_addr.get("name"):
        addr_lines.append(f"<strong>{ship_addr['name']}</strong>")
    if ship_addr.get("company"):
        addr_lines.append(ship_addr["company"])
    if ship_addr.get("line1"):
        addr_lines.append(ship_addr["line1"])
    if ship_addr.get("line2"):
        addr_lines.append(ship_addr["line2"])
    csz = ""
    if ship_addr.get("city"):
        csz = ship_addr["city"]
    if ship_addr.get("state"):
        csz += f", {ship_addr['state']}"
    if ship_addr.get("zip"):
        csz += f" {ship_addr['zip']}"
    if csz:
        addr_lines.append(csz)
    if ship_addr.get("phone"):
        addr_lines.append(f"Phone: {ship_addr['phone']}")

    shipping_html = "<br>".join(addr_lines) if addr_lines else "<em>No shipping address on file — we'll confirm before shipping.</em>"

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;">
        <div style="background:#1a1a2e;color:#fff;padding:24px 28px;border-radius:8px 8px 0 0;">
            <h1 style="margin:0;font-size:22px;">Keith Enterprises</h1>
            <p style="margin:6px 0 0;opacity:0.8;font-size:14px;">Order Confirmation</p>
        </div>
        <div style="background:#fff;padding:28px;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 8px 8px;">
            <p style="font-size:16px;">Hi {buyer or 'there'},</p>
            <p>Thank you for your order. Here is your confirmation:</p>

            <table style="width:100%;margin:12px 0;">
                <tr><td style="color:#666;padding:3px 0;width:130px;">Order ID</td><td style="font-weight:bold;">{order_id}</td></tr>
                <tr><td style="color:#666;padding:3px 0;">Date</td><td>{order.get('created_at', '—')}</td></tr>
                <tr><td style="color:#666;padding:3px 0;">Payment Terms</td><td>{order.get('payment_terms', 'Wire before ship')}</td></tr>
            </table>

            <h3 style="margin:20px 0 8px;border-bottom:2px solid #1a1a2e;padding-bottom:4px;">Order Details</h3>
            <table style="width:100%;border-collapse:collapse;">
                <thead>
                    <tr style="background:#f5f5f5;">
                        <th style="padding:10px 12px;text-align:left;">Product</th>
                        <th style="padding:10px 12px;text-align:center;">Qty</th>
                        <th style="padding:10px 12px;text-align:right;">Unit Cost</th>
                        <th style="padding:10px 12px;text-align:right;">Line Total</th>
                    </tr>
                </thead>
                <tbody>
                    {items_rows}
                </tbody>
                <tfoot>
                    <tr style="background:#f0f7f4;font-weight:bold;">
                        <td colspan="3" style="padding:10px 12px;text-align:right;">Subtotal</td>
                        <td style="padding:10px 12px;text-align:right;font-size:18px;color:#2d6a4f;">${subtotal:,.2f}</td>
                    </tr>
                </tfoot>
            </table>

            <!-- Shipping Address -->
            <div style="display:flex;gap:24px;margin:24px 0;">
                <div style="flex:1;background:#f9f9f9;padding:16px;border-radius:6px;">
                    <p style="margin:0 0 8px;font-size:11px;color:#999;text-transform:uppercase;letter-spacing:1px;font-weight:bold;">Ship To</p>
                    <p style="margin:0;font-size:14px;line-height:1.6;">{shipping_html}</p>
                </div>
            </div>

            <!-- Payment Details -->
            <div style="background:#fff8e1;border-left:4px solid #f9a825;padding:16px;margin:20px 0;border-radius:0 4px 4px 0;">
                <p style="margin:0;font-weight:bold;color:#f57f17;">Payment Information</p>
                <table style="margin:10px 0 0;font-size:14px;line-height:1.8;">
                    <tr><td style="color:#666;padding:2px 16px 2px 0;">Amount Due:</td><td style="font-weight:bold;">${subtotal:,.2f}</td></tr>
                    <tr><td style="color:#666;padding:2px 16px 2px 0;">Terms:</td><td>{order.get('payment_terms', 'Wire before ship')}</td></tr>
                    <tr><td style="color:#666;padding:2px 16px 2px 0;">Wire Transfer:</td><td>Contact us for bank details</td></tr>
                    <tr><td style="color:#666;padding:2px 16px 2px 0;">Zelle:</td><td>jaxonbelgiano@gmail.com</td></tr>
                    <tr><td style="color:#666;padding:2px 16px 2px 0;">Reference:</td><td style="font-weight:bold;">{order_id}</td></tr>
                </table>
                <p style="margin:10px 0 0;font-size:12px;color:#666;">Please include your order number with your payment for faster processing.</p>
            </div>

            <!-- Next Steps -->
            <div style="background:#f0f7f4;border-left:4px solid #2d6a4f;padding:16px;margin:20px 0;border-radius:0 4px 4px 0;">
                <p style="margin:0;font-weight:bold;color:#2d6a4f;">What Happens Next</p>
                <ol style="margin:8px 0 0;padding-left:20px;font-size:14px;line-height:1.8;">
                    <li>We confirm product availability (within 24 hours)</li>
                    <li>You send payment via wire or Zelle</li>
                    <li>We arrange shipping once payment clears</li>
                    <li>You receive tracking information via email</li>
                </ol>
            </div>

            <p style="color:#888;font-size:12px;margin-top:24px;border-top:1px solid #eee;padding-top:12px;">
                Quantities are held for 48 hours. If you have questions, reply to this email.<br>
                Keith Enterprises — Wholesale Distribution
            </p>
        </div>
    </div>
    """

    return _smtp_send(buyer_email, subject, html)


def send_invoice_email(order, buyer_email, invoice_html=""):
    """Send an invoice HTML email to the buyer with line items and payment info."""
    order_id = order.get("id", "N/A")
    buyer = order.get("buyer_name", "")
    subtotal = order.get("subtotal", 0)
    items = order.get("items", [])
    created = order.get("created_at", "")

    subject = f"Keith Enterprises — Invoice {order_id} — ${subtotal:,.2f}"

    # Build line items table
    items_html = ""
    for i, item in enumerate(items, 1):
        qty = item.get("qty", 0)
        unit = item.get("unit_cost", 0)
        total = item.get("line_total", qty * unit)
        items_html += f"""<tr>
            <td style="padding:10px 14px;border-bottom:1px solid #30363d;color:#e6edf3;">{i}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #30363d;color:#e6edf3;">{item.get('product_name','')}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #30363d;color:#8b949e;font-size:0.8rem;">{item.get('upc','')}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #30363d;color:#e6edf3;text-align:center;">{qty:,}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #30363d;color:#e6edf3;text-align:right;">${unit:.2f}</td>
            <td style="padding:10px 14px;border-bottom:1px solid #30363d;color:#3fb950;text-align:right;font-weight:600;">${total:,.2f}</td>
        </tr>"""

    # Shipping address
    ship = order.get("shipping_address", {})
    ship_lines = [s for s in [
        ship.get("name", ""), ship.get("company", ""), ship.get("line1", ""),
        ship.get("line2", ""),
        f"{ship.get('city', '')}, {ship.get('state', '')} {ship.get('zip', '')}".strip(", "),
        f"Phone: {ship.get('phone', '')}" if ship.get("phone") else "",
    ] if s and s.strip()]
    ship_html = "<br>".join(ship_lines) if ship_lines else "To be confirmed"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="background:#0f1117;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;margin:0;padding:0;">
<div style="max-width:700px;margin:0 auto;padding:32px 20px;">

    <h2 style="color:#e6edf3;margin:0 0 4px;font-size:1.3rem;">Keith Enterprises — Invoice</h2>
    <p style="color:#8b949e;margin:0 0 24px;font-size:0.85rem;">Order {order_id} &bull; {created}</p>

    <p style="color:#e6edf3;margin:0 0 20px;">Hi {buyer or 'there'},</p>

    <div style="overflow-x:auto;border:1px solid #30363d;border-radius:8px;">
    <table style="width:100%;border-collapse:collapse;background:#1c2128;">
        <thead><tr style="background:#161b22;">
            <th style="padding:10px 14px;text-align:left;color:#8b949e;font-size:0.8rem;width:30px;">#</th>
            <th style="padding:10px 14px;text-align:left;color:#8b949e;font-size:0.8rem;">Product</th>
            <th style="padding:10px 14px;text-align:left;color:#8b949e;font-size:0.8rem;">UPC</th>
            <th style="padding:10px 14px;text-align:center;color:#8b949e;font-size:0.8rem;">Qty</th>
            <th style="padding:10px 14px;text-align:right;color:#8b949e;font-size:0.8rem;">Unit Price</th>
            <th style="padding:10px 14px;text-align:right;color:#8b949e;font-size:0.8rem;">Total</th>
        </tr></thead>
        <tbody>{items_html}</tbody>
        <tfoot><tr style="background:#161b22;">
            <td colspan="5" style="padding:12px 14px;text-align:right;color:#e6edf3;font-weight:600;font-size:1rem;">Invoice Total:</td>
            <td style="padding:12px 14px;text-align:right;color:#3fb950;font-weight:700;font-size:1.1rem;">${subtotal:,.2f}</td>
        </tr></tfoot>
    </table>
    </div>

    <div style="display:flex;gap:16px;margin-top:20px;flex-wrap:wrap;">
        <div style="flex:1;min-width:250px;background:#1c2128;border:1px solid #30363d;border-radius:8px;padding:16px;">
            <p style="margin:0 0 8px;font-size:0.75rem;color:#8b949e;text-transform:uppercase;letter-spacing:1px;font-weight:600;">Ship To</p>
            <p style="margin:0;color:#e6edf3;font-size:0.85rem;line-height:1.6;">{ship_html}</p>
        </div>
        <div style="flex:1;min-width:250px;background:#d2992215;border:1px solid #d2992240;border-radius:8px;padding:16px;">
            <p style="margin:0 0 8px;font-size:0.75rem;color:#d29922;text-transform:uppercase;letter-spacing:1px;font-weight:600;">Payment Details</p>
            <table style="font-size:0.85rem;line-height:1.8;color:#e6edf3;">
                <tr><td style="color:#8b949e;padding:2px 12px 2px 0;">Amount Due:</td><td style="font-weight:700;color:#3fb950;">${subtotal:,.2f}</td></tr>
                <tr><td style="color:#8b949e;padding:2px 12px 2px 0;">Terms:</td><td>{order.get('payment_terms', 'Wire before ship')}</td></tr>
                <tr><td style="color:#8b949e;padding:2px 12px 2px 0;">Zelle:</td><td>jaxonbelgiano@gmail.com</td></tr>
                <tr><td style="color:#8b949e;padding:2px 12px 2px 0;">Reference:</td><td style="font-weight:600;">{order_id}</td></tr>
            </table>
            <p style="margin:10px 0 0;font-size:0.75rem;color:#8b949e;">Include your order number with payment.</p>
        </div>
    </div>

    <p style="color:#8b949e;font-size:0.8rem;margin:20px 0 0;">If you have any questions, reply to this email.</p>
    <p style="color:#e6edf3;margin:16px 0 0;">Best,</p>
    <p style="color:#e6edf3;margin:4px 0 0;font-weight:600;">Keith Enterprises</p>

</div>
</body></html>"""

    return _smtp_send(buyer_email, subject, html)
