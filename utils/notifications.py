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
                <tr><td style="color:#666;padding:3px 0;width:120px;">Order ID</td><td style="font-weight:bold;">{order_id}</td></tr>
                <tr><td style="color:#666;padding:3px 0;">Date</td><td>{order.get('created_at', '—')}</td></tr>
                <tr><td style="color:#666;padding:3px 0;">Payment Terms</td><td>{order.get('payment_terms', '—')}</td></tr>
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

            <div style="background:#f0f7f4;border-left:4px solid #2d6a4f;padding:16px;margin:24px 0;border-radius:0 4px 4px 0;">
                <p style="margin:0;font-weight:bold;color:#2d6a4f;">Next Steps</p>
                <p style="margin:8px 0 0;">We'll confirm availability and send payment details within 24 hours.</p>
            </div>

            <p style="color:#888;font-size:12px;margin-top:24px;border-top:1px solid #eee;padding-top:12px;">
                If you have questions about this order, reply to this email or contact us directly.
            </p>
        </div>
    </div>
    """

    return _smtp_send(buyer_email, subject, html)


def send_invoice_email(order, buyer_email, invoice_html):
    """Send an invoice HTML email to the buyer.

    The invoice_html is pre-rendered HTML content passed in by the caller.
    """
    order_id = order.get("id", "N/A")
    buyer = order.get("buyer_name", "")
    subtotal = order.get("subtotal", 0)

    subject = f"Invoice for Order {order_id} — ${subtotal:,.2f}"

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;">
        <div style="background:#1a1a2e;color:#fff;padding:20px 24px;border-radius:8px 8px 0 0;">
            <h2 style="margin:0;">Keith Enterprises — Invoice</h2>
            <p style="margin:6px 0 0;opacity:0.8;font-size:14px;">Order {order_id}</p>
        </div>
        <div style="background:#fff;padding:24px;border:1px solid #e0e0e0;border-top:none;">
            <p>Hi {buyer or 'there'},</p>
            <p>Please find your invoice below for order <strong>{order_id}</strong>.</p>
        </div>
        <div style="padding:0 24px 24px;background:#fff;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 8px 8px;">
            {invoice_html}
            <div style="margin-top:24px;padding-top:16px;border-top:1px solid #eee;">
                <p style="color:#666;font-size:13px;">
                    Payment Terms: {order.get('payment_terms', '—')}<br>
                    If you have any questions, reply to this email.
                </p>
            </div>
        </div>
    </div>
    """

    return _smtp_send(buyer_email, subject, html)
