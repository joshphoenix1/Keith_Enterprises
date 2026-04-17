"""Marketplace price lookup — fetches Amazon & Walmart prices for offers.

Uses product name / UPC to search marketplaces and extract current pricing.
"""

import json
import os
import logging
import re
import time
import requests
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
logger = logging.getLogger("keith.pricing")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return []


def _save_json(filename, data):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _extract_pack_qty(offer):
    """Extract pack quantity from offer notes (e.g. '12/case', '24/case', '12pk')."""
    notes = offer.get("notes", "") or ""
    # Try various formats: 12/case, 12pk, 12-pack, pack of 12
    for pattern in [r'(\d+)/case', r'(\d+)pk', r'(\d+)-pack', r'pack\s*(?:of\s*)?(\d+)',
                    r'(\d+)\s*(?:per|units?\s+per)\s*case']:
        match = re.search(pattern, notes, re.IGNORECASE)
        if match:
            return int(match.group(1))
    # Also check if pack_qty was set directly
    return offer.get("pack_qty", 0) or 0


def search_amazon_price(product_name, upc=""):
    """Search Amazon for a product and extract price via Claude.

    Tries UPC first (more precise), falls back to product name search.
    Returns dict with amazon_price or error.
    """
    from utils.vision import _claude_call, _parse_json_response

    query = upc if upc else product_name
    search_url = f"https://www.amazon.com/s?k={requests.utils.quote(query)}"

    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            # Try with product name if UPC failed
            if upc and product_name:
                search_url = f"https://www.amazon.com/s?k={requests.utils.quote(product_name)}"
                resp = requests.get(search_url, headers=HEADERS, timeout=15)

        page_text = resp.text

        # Strip HTML to get text content (rough)
        text = re.sub(r'<script[^>]*>.*?</script>', '', page_text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        if len(text) < 200:
            return {"error": "Empty search results page"}

        prompt = f"""I searched Amazon for: "{product_name}" (UPC: {upc})

Here is the search results page text (truncated):
{text[:6000]}

Find the price for the most relevant matching product. Return JSON:
{{"amazon_price": 29.99, "product_match": "Exact product name found", "confidence": "high/medium/low"}}

If no matching product found, return:
{{"amazon_price": null, "error": "No match found"}}

Only return valid JSON."""

        response = _claude_call(prompt, timeout=60)
        result = _parse_json_response(response)
        return result

    except Exception as e:
        logger.error("Amazon search error for %s: %s", product_name[:40], e)
        return {"error": str(e)}


def search_walmart_price(product_name, upc=""):
    """Search Walmart for a product and extract price via Claude.

    Returns dict with walmart_price or error.
    """
    from utils.vision import _claude_call, _parse_json_response

    query = upc if upc else product_name
    search_url = f"https://www.walmart.com/search?q={requests.utils.quote(query)}"

    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        page_text = resp.text

        text = re.sub(r'<script[^>]*>.*?</script>', '', page_text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        if len(text) < 200:
            return {"error": "Empty search results page"}

        prompt = f"""I searched Walmart for: "{product_name}" (UPC: {upc})

Here is the search results page text (truncated):
{text[:6000]}

Find the price for the most relevant matching product. Return JSON:
{{"walmart_price": 24.99, "product_match": "Exact product name found", "confidence": "high/medium/low"}}

If no matching product found, return:
{{"walmart_price": null, "error": "No match found"}}

Only return valid JSON."""

        response = _claude_call(prompt, timeout=60)
        result = _parse_json_response(response)
        return result

    except Exception as e:
        logger.error("Walmart search error for %s: %s", product_name[:40], e)
        return {"error": str(e)}


def lookup_prices(offer):
    """Look up Amazon and Walmart prices for a single offer.

    Updates the offer's marketplace_data in-place.
    Returns the marketplace_data dict.
    """
    product_name = offer.get("product_name", "")
    upc = offer.get("upc", "")

    if not product_name:
        return offer.get("marketplace_data", {})

    mp = offer.setdefault("marketplace_data", {})

    # Amazon
    if not mp.get("amazon_price"):
        amazon = search_amazon_price(product_name, upc)
        if amazon.get("amazon_price"):
            mp["amazon_price"] = float(amazon["amazon_price"])
            mp["amazon_match"] = amazon.get("product_match", "")
            mp["amazon_confidence"] = amazon.get("confidence", "")
            logger.info("Amazon price for %s: $%.2f", product_name[:30], mp["amazon_price"])

    # Walmart — skip for now, blocks scrapers. Will use API when available.
    # if not mp.get("walmart_price"):
    #     walmart = search_walmart_price(product_name, upc)
    #     if walmart.get("walmart_price"):
    #         mp["walmart_price"] = float(walmart["walmart_price"])
    #         mp["walmart_match"] = walmart.get("product_match", "")
    #         mp["walmart_confidence"] = walmart.get("confidence", "")
    #         logger.info("Walmart price for %s: $%.2f", product_name[:30], mp["walmart_price"])

    # Calculate margin if we have prices
    # Offered price is per case — extract pack qty from notes (e.g. "12/case")
    offered = offer.get("offered_price") or 0
    pack_qty = _extract_pack_qty(offer)
    if pack_qty and offered:
        per_unit_cost = offered / pack_qty
        offer["per_unit_cost"] = round(per_unit_cost, 2)
        offer["pack_qty"] = pack_qty
    else:
        per_unit_cost = offered

    best_price = mp.get("amazon_price") or mp.get("walmart_price")
    if best_price and per_unit_cost and best_price > 0:
        margin = ((best_price - per_unit_cost) / best_price) * 100
        offer["margin_pct"] = round(margin, 1)

    mp["last_checked"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return mp


def bulk_lookup_prices(max_offers=20, delay=2):
    """Look up prices for offers that don't have marketplace data yet.

    Args:
        max_offers: max number of offers to process in one run
        delay: seconds between lookups to avoid rate limiting

    Returns:
        dict with counts of processed/found prices
    """
    offers = _load_json("offers.json")
    if not isinstance(offers, list):
        return {"processed": 0}

    # Find offers needing price lookup
    needs_lookup = []
    for o in offers:
        mp = o.get("marketplace_data") or {}
        if not mp.get("amazon_price") and not mp.get("walmart_price"):
            needs_lookup.append(o)

    needs_lookup = needs_lookup[:max_offers]
    logger.info("Price lookup: %d offers need prices (%d will process now)",
                sum(1 for o in offers if not (o.get("marketplace_data") or {}).get("amazon_price")),
                len(needs_lookup))

    amazon_found = 0
    walmart_found = 0

    for i, offer in enumerate(needs_lookup):
        try:
            mp = lookup_prices(offer)
            if mp.get("amazon_price"):
                amazon_found += 1
            if mp.get("walmart_price"):
                walmart_found += 1
            logger.info("  [%d/%d] %s — AMZ: $%s, WMT: $%s",
                        i + 1, len(needs_lookup),
                        offer["product_name"][:30],
                        mp.get("amazon_price", "—"),
                        mp.get("walmart_price", "—"))
        except Exception as e:
            logger.error("Price lookup failed for %s: %s",
                         offer.get("product_name", "?")[:30], e)

        if i < len(needs_lookup) - 1:
            time.sleep(delay)

    _save_json("offers.json", offers)

    return {
        "processed": len(needs_lookup),
        "amazon_found": amazon_found,
        "walmart_found": walmart_found,
        "remaining": sum(1 for o in offers
                         if not (o.get("marketplace_data") or {}).get("amazon_price")) - len(needs_lookup),
    }
