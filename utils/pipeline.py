"""
Pipeline utility for auto-creating offers from scanned inbox products.
Reads inbox messages, extracts products from scan_results and products fields,
and creates offer entries in offers.json (deduplicating by product_name).
"""

import json
import os
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def _load_json(filename):
    """Load a JSON file from DATA_DIR, returning default on error."""
    path = os.path.join(DATA_DIR, filename)
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return [] if filename != "inbox.json" else {"messages": []}


def _save_json(filename, data):
    """Save data to a JSON file in DATA_DIR."""
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _next_offer_id(offers):
    """Return the next available offer ID."""
    if not offers:
        return 1
    return max(o.get("id", 0) for o in offers) + 1


def create_offer_from_scan(scan_result, source_msg):
    """
    Create a single offer dict from a scan result and the source message.

    Args:
        scan_result: dict with keys like product_name, brand, category, upc,
                     price_offered, quantity (from scan_results or products list)
        source_msg: the inbox message dict this product came from

    Returns:
        dict: an offer entry ready to be appended to offers.json
    """
    now = datetime.now()
    expiry = (now + timedelta(days=7)).strftime("%Y-%m-%d")

    return {
        "id": None,  # caller assigns the actual ID
        "upc": scan_result.get("upc") or scan_result.get("upc_barcode", ""),
        "product_name": scan_result.get("product_name") or scan_result.get("name", "Unknown Product"),
        "category": scan_result.get("category", ""),
        "quantity": scan_result.get("quantity", 0),
        "offered_price": scan_result.get("offered_price") or scan_result.get("price_offered", 0),
        "expiry": expiry,
        "source": source_msg.get("source", ""),
        "source_from": source_msg.get("sender_name") or source_msg.get("from", ""),
        "status": "new",
        "marketplace_data": {
            "amazon_price": None,
            "walmart_price": None,
        },
        "matched_buyers": [],
        "margin_pct": None,
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "notes": f"Auto-created from inbox message #{source_msg.get('id', '?')}",
    }


def log_activity(activity_type, action, detail):
    """
    Append an activity entry to activity.json with current timestamp.

    Args:
        activity_type: str, e.g. "pipeline", "offer", "scan"
        action: str, e.g. "created_offer", "ingested_products"
        detail: str, human-readable description
    """
    activities = _load_json("activity.json")
    if not isinstance(activities, list):
        activities = []

    activities.append({
        "type": activity_type,
        "action": action,
        "detail": detail,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })

    _save_json("activity.json", activities)


def auto_match_buyers(offers=None):
    """Match buyers to offers based on category, quantity, and margin.

    For each offer without matched buyers, finds buyers whose category list
    includes the offer's category, respects min/max quantity thresholds,
    and checks margin if marketplace pricing exists.

    Args:
        offers: list of offer dicts (modified in-place). If None, loads from disk.

    Returns:
        int: number of offers that got at least one buyer matched.
    """
    buyers = _load_json("buyers.json")
    if not isinstance(buyers, list) or not buyers:
        return 0

    if offers is None:
        offers = _load_json("offers.json")
        if not isinstance(offers, list):
            return 0

    matched_count = 0

    for offer in offers:
        # Skip offers that already have matched buyers or are rejected
        if offer.get("matched_buyers") and len(offer["matched_buyers"]) > 0:
            continue
        if offer.get("status") == "rejected":
            continue

        offer_cat = (offer.get("category") or "").strip()
        offer_qty = offer.get("quantity") or 0
        offer_price = offer.get("offered_price") or 0

        matched = []
        for buyer in buyers:
            buyer_cats = [c.strip() for c in buyer.get("categories", [])]

            # Category match — check if offer category matches any buyer category
            cat_match = False
            if not buyer_cats or "Other" in buyer_cats:
                cat_match = True  # Buyer accepts all categories
            elif offer_cat:
                # Check direct match or partial match
                for bc in buyer_cats:
                    if bc.lower() == offer_cat.lower():
                        cat_match = True
                        break
                # Also try mapping common category names
                cat_map = {
                    "immune": "OTC", "joint": "OTC", "digestive": "OTC",
                    "vitamins": "OTC", "supplements": "OTC", "sleep": "OTC",
                    "beauty": "HBA", "skincare": "HBA", "cosmetics": "HBA",
                    "personal care": "HBA", "hair care": "HBA",
                    "candles": "Household", "home": "Household",
                    "games": "Toys", "toys": "Toys",
                    "food": "Grocery", "beverage": "Grocery",
                }
                mapped = cat_map.get(offer_cat.lower(), "")
                if mapped and mapped in buyer_cats:
                    cat_match = True

            if not cat_match:
                continue

            # Quantity check
            min_qty = buyer.get("min_qty") or 0
            max_qty = buyer.get("max_qty") or 0
            if min_qty and offer_qty and offer_qty < min_qty:
                continue
            if max_qty and offer_qty and offer_qty > max_qty:
                continue

            # Margin check (if marketplace data exists)
            target_margin = buyer.get("target_margin_pct") or 0
            if target_margin and offer_price:
                amazon_price = (offer.get("marketplace_data") or {}).get("amazon_price")
                if amazon_price and amazon_price > 0:
                    margin = ((amazon_price - offer_price) / amazon_price) * 100
                    offer["margin_pct"] = round(margin, 1)
                    if margin < target_margin:
                        continue

            matched.append({
                "buyer_id": buyer.get("id"),
                "buyer_name": buyer.get("name", ""),
                "rep": buyer.get("rep", ""),
                "contact_email": buyer.get("contact_email", ""),
                "phone": buyer.get("phone", ""),
                "matched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "match_reason": f"Category: {offer_cat}" + (
                    f", margin OK" if target_margin else ""),
            })

        if matched:
            offer["matched_buyers"] = matched
            offer["status"] = "matched"
            matched_count += 1

    return matched_count


def ingest_products_from_inbox():
    """
    Scan all inbox messages, find products (from msg.products and
    msg.scan_results where is_product=True), and create offer entries
    for any not already in offers.json. Deduplicates by product_name.

    Returns:
        dict: {"scanned": int, "new_offers": int, "duplicates": int}
    """
    inbox = _load_json("inbox.json")
    offers = _load_json("offers.json")
    if not isinstance(offers, list):
        offers = []

    # Build set of existing product names for deduplication
    existing_names = {
        o.get("product_name", "").strip().lower()
        for o in offers
        if o.get("product_name")
    }

    new_offers = []
    scanned = 0
    duplicates = 0
    next_id = _next_offer_id(offers)

    messages = inbox.get("messages", [])

    for msg in messages:
        # Collect candidate products from both sources
        candidates = []

        # From scan_results: only where is_product is True
        for sr in msg.get("scan_results", []):
            if sr.get("is_product"):
                candidates.append(sr)

        # From products list: all entries are considered products
        for prod in msg.get("products", []):
            candidates.append(prod)

        for candidate in candidates:
            scanned += 1
            name = (
                candidate.get("product_name")
                or candidate.get("name")
                or ""
            ).strip()

            if not name:
                continue

            name_lower = name.lower()
            if name_lower in existing_names:
                duplicates += 1
                continue

            # Create the offer
            offer = create_offer_from_scan(candidate, msg)
            offer["id"] = next_id
            next_id += 1

            new_offers.append(offer)
            existing_names.add(name_lower)

    # Persist
    if new_offers:
        offers.extend(new_offers)
        _save_json("offers.json", offers)

    # Auto-match buyers to new offers
    matched_count = 0
    if new_offers:
        matched_count = auto_match_buyers(offers)
        if matched_count:
            _save_json("offers.json", offers)

    # Log activity
    if scanned > 0 or new_offers:
        log_activity(
            "pipeline",
            "ingested_products",
            f"Scanned {scanned} products from inbox. "
            f"Created {len(new_offers)} new offers, {duplicates} duplicates skipped. "
            f"Matched {matched_count} offers to buyers.",
        )

    return {
        "scanned": scanned,
        "new_offers": len(new_offers),
        "duplicates": duplicates,
        "matched": matched_count,
    }
