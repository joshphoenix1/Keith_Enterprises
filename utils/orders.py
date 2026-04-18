"""Order and hold management for the wholesale pipeline.

Handles:
- Quantity holds (48-hour soft reservations when offers are sent to buyers)
- Order creation from buyer acceptances
- Order status management
- Dynamic availability calculation
"""

import json
import os
import logging
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
ORDERS_PATH = os.path.join(DATA_DIR, "orders.json")
HOLDS_PATH = os.path.join(DATA_DIR, "holds.json")
OFFERS_PATH = os.path.join(DATA_DIR, "offers.json")

logger = logging.getLogger("keith.orders")

HOLD_DURATION_HOURS = 48
ORDER_PENDING_EXPIRY_HOURS = 48


def _load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default if default is not None else []


def _save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ── Holds ──

def create_holds(offer_ids, buyer_id, buyer_name):
    """Create 48-hour holds on offers when they're sent to a buyer.

    Returns list of created hold dicts.
    """
    holds = _load_json(HOLDS_PATH, [])
    now = datetime.now()
    expires = now + timedelta(hours=HOLD_DURATION_HOURS)
    created = []

    for oid in offer_ids:
        # Don't duplicate holds for same buyer+offer
        existing = next((h for h in holds
                         if h["offer_id"] == oid and h["buyer_id"] == buyer_id
                         and h.get("status") == "active"), None)
        if existing:
            # Refresh expiry
            existing["expires_at"] = expires.strftime("%Y-%m-%d %H:%M")
            created.append(existing)
            continue

        hold = {
            "offer_id": oid,
            "buyer_id": buyer_id,
            "buyer_name": buyer_name,
            "status": "active",  # active, converted, expired
            "created_at": now.strftime("%Y-%m-%d %H:%M"),
            "expires_at": expires.strftime("%Y-%m-%d %H:%M"),
        }
        holds.append(hold)
        created.append(hold)

    _save_json(HOLDS_PATH, holds)
    logger.info("Created %d holds for buyer %s", len(created), buyer_name)
    return created


def expire_holds():
    """Expire any holds past their 48-hour window. Returns count expired."""
    holds = _load_json(HOLDS_PATH, [])
    now = datetime.now()
    expired = 0

    for h in holds:
        if h.get("status") == "active":
            try:
                exp = datetime.strptime(h["expires_at"], "%Y-%m-%d %H:%M")
                if now > exp:
                    h["status"] = "expired"
                    expired += 1
            except (ValueError, KeyError):
                pass

    if expired:
        _save_json(HOLDS_PATH, holds)
        logger.info("Expired %d holds", expired)
    return expired


def convert_holds_to_order(offer_ids, buyer_id):
    """Convert active holds to 'converted' status when an order is placed."""
    holds = _load_json(HOLDS_PATH, [])
    converted = 0

    for h in holds:
        if (h.get("offer_id") in offer_ids and h.get("buyer_id") == buyer_id
                and h.get("status") == "active"):
            h["status"] = "converted"
            converted += 1

    _save_json(HOLDS_PATH, holds)
    return converted


def expire_stale_orders():
    """Auto-cancel pending_review orders older than 48 hours.

    Returns count of orders cancelled.
    """
    orders = _load_json(ORDERS_PATH, [])
    now = datetime.now()
    cancelled = 0

    for order in orders:
        if order.get("status") != "pending_review":
            continue
        try:
            created = datetime.fromisoformat(order["created_at"])
            if now - created > timedelta(hours=ORDER_PENDING_EXPIRY_HOURS):
                order["status"] = "cancelled"
                order["cancelled_reason"] = "auto-expired after 48h pending_review"
                cancelled += 1
        except (ValueError, KeyError):
            pass

    if cancelled:
        _save_json(ORDERS_PATH, orders)
        logger.info("Auto-cancelled %d stale pending_review orders", cancelled)
    return cancelled


def get_available_qty(offer_id):
    """Calculate available quantity for an offer accounting for holds and orders.

    available = total_qty - sum(active_hold_qtys) - sum(ordered_qtys)
    """
    # Expire stale holds and orders first
    expire_holds()
    expire_stale_orders()

    offers = _load_json(OFFERS_PATH, [])
    offer = next((o for o in offers if o.get("id") == offer_id), None)
    if not offer:
        return 0

    total = offer.get("quantity", 0)

    # Subtract ordered quantities
    orders = _load_json(ORDERS_PATH, [])
    ordered = 0
    for order in orders:
        if order.get("status") in ("cancelled",):
            continue
        for item in order.get("items", []):
            if item.get("offer_id") == offer_id:
                ordered += item.get("qty", 0)

    available = max(0, total - ordered)
    return available


def get_available_qty_bulk(offer_ids):
    """Get available quantities for multiple offers efficiently."""
    expire_holds()
    expire_stale_orders()

    offers = _load_json(OFFERS_PATH, [])
    orders = _load_json(ORDERS_PATH, [])

    # Build qty map
    total_map = {}
    for o in offers:
        if o.get("id") in offer_ids:
            total_map[o["id"]] = o.get("quantity", 0)

    # Sum ordered quantities per offer
    ordered_map = {}
    for order in orders:
        if order.get("status") in ("cancelled",):
            continue
        for item in order.get("items", []):
            oid = item.get("offer_id")
            if oid in offer_ids:
                ordered_map[oid] = ordered_map.get(oid, 0) + item.get("qty", 0)

    result = {}
    for oid in offer_ids:
        total = total_map.get(oid, 0)
        ordered = ordered_map.get(oid, 0)
        result[oid] = max(0, total - ordered)

    return result


# ── Orders ──

def _next_order_id():
    """Generate next order ID like ORD-20260417-001."""
    orders = _load_json(ORDERS_PATH, [])
    today = datetime.now().strftime("%Y%m%d")
    today_orders = [o for o in orders if o.get("id", "").startswith(f"ORD-{today}")]
    seq = len(today_orders) + 1
    return f"ORD-{today}-{seq:03d}"


def create_order(buyer_id, buyer_name, buyer_email, accepted_items, payment_terms="Wire before ship"):
    """Create an order from accepted offer items.

    Args:
        buyer_id: buyer ID
        buyer_name: buyer display name
        buyer_email: buyer email
        accepted_items: list of dicts with offer_id, product_name, upc, unit_cost, qty
        payment_terms: payment terms string

    Returns:
        order dict
    """
    orders = _load_json(ORDERS_PATH, [])
    now = datetime.now()

    items = []
    subtotal = 0
    for item in accepted_items:
        line_total = round(item["unit_cost"] * item["qty"], 2)
        items.append({
            "offer_id": item["offer_id"],
            "product_name": item["product_name"],
            "upc": item.get("upc", ""),
            "unit_cost": item["unit_cost"],
            "qty": item["qty"],
            "line_total": line_total,
        })
        subtotal += line_total

    order = {
        "id": _next_order_id(),
        "buyer_id": buyer_id,
        "buyer_name": buyer_name,
        "buyer_email": buyer_email,
        "status": "pending_review",  # pending_review, confirmed, invoiced, paid, shipped, completed, cancelled
        "items": items,
        "subtotal": round(subtotal, 2),
        "payment_terms": payment_terms,
        "payment_status": "unpaid",  # unpaid, partial, paid
        "shipping_status": "not_shipped",  # not_shipped, shipped, delivered
        "tracking_number": "",
        "carrier": "",
        "created_at": now.strftime("%Y-%m-%d %H:%M"),
        "confirmed_at": None,
        "paid_at": None,
        "shipped_at": None,
        "notes": "",
    }

    orders.append(order)
    _save_json(ORDERS_PATH, orders)

    # Convert holds
    offer_ids = [item["offer_id"] for item in accepted_items]
    convert_holds_to_order(offer_ids, buyer_id)

    # Log activity
    try:
        from utils.pipeline import log_activity
        log_activity("order", "created",
                     f"Order {order['id']} from {buyer_name}: {len(items)} items, ${subtotal:,.2f}")
    except Exception:
        pass

    logger.info("Created order %s: %d items, $%.2f", order["id"], len(items), subtotal)
    return order


def load_orders():
    return _load_json(ORDERS_PATH, [])


def save_orders(orders):
    _save_json(ORDERS_PATH, orders)


def update_order_status(order_id, status):
    """Update an order's status."""
    orders = _load_json(ORDERS_PATH, [])
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    for o in orders:
        if o.get("id") == order_id:
            o["status"] = status
            if status == "confirmed":
                o["confirmed_at"] = now
            elif status == "paid":
                o["payment_status"] = "paid"
                o["paid_at"] = now
            elif status == "shipped":
                o["shipping_status"] = "shipped"
                o["shipped_at"] = now
            elif status == "completed":
                o["shipping_status"] = "delivered"
            _save_json(ORDERS_PATH, orders)
            return o
    return None
