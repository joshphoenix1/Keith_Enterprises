"""Seller Assistant API integration for product enrichment.

Converts UPC → ASIN, then pulls full product data including:
- Buy Box price, FBA/FBM prices
- FBA fees (fulfillment, referral, storage, inbound)
- Restriction status (allowed/not eligible/approval required)
- BSR, estimated monthly sales
- Competitor counts
- Risk flags (hazmat, meltable, oversize, etc.)
"""

import json
import os
import time
import logging
import threading
import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
ACCOUNTS_PATH = os.path.join(DATA_DIR, "accounts.json")

logger = logging.getLogger("keith.seller_assistant")

BASE_URL = "https://app.sellerassistant.app/api/v1"
DOMAIN = "amazon.com"


def _get_api_key():
    try:
        with open(ACCOUNTS_PATH) as f:
            accounts = json.load(f)
        return accounts.get("seller_assistant", {}).get("api_key", "")
    except Exception:
        return ""


def _headers():
    return {"X-Api-Key": _get_api_key()}


def upc_to_asin(upc):
    """Convert a UPC/EAN to ASIN(s). Returns list of ASIN strings."""
    if not upc:
        return []
    try:
        resp = requests.get(
            f"{BASE_URL}/converters/identifier-to-asins",
            params={"identifier": upc, "domain": DOMAIN},
            headers=_headers(), timeout=15,
        )
        resp.raise_for_status()
        results = resp.json()
        return [r["identifier"] for r in results if r.get("identifierType") == "ASIN"]
    except Exception as e:
        logger.error("UPC to ASIN failed for %s: %s", upc, e)
        return []


def get_product_info(asin):
    """Get full product info from Seller Assistant.

    Returns dict with all product data or None on error.
    """
    if not asin:
        return None
    try:
        resp = requests.get(
            f"{BASE_URL}/products/{asin}",
            params={"domain": DOMAIN},
            headers=_headers(), timeout=15,
        )
        if resp.status_code == 404:
            return None
        if resp.status_code == 429:
            logger.warning("Rate limited, waiting 60s...")
            time.sleep(60)
            resp = requests.get(
                f"{BASE_URL}/products/{asin}",
                params={"domain": DOMAIN},
                headers=_headers(), timeout=15,
            )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error("Product info failed for %s: %s", asin, e)
        return None


def enrich_offer(offer):
    """Enrich a single offer with Seller Assistant data.

    Looks up by UPC → ASIN → full product data.
    Updates the offer dict in-place with SA data.
    Returns the enriched offer.
    """
    upc = offer.get("upc", "")
    sa_data = offer.get("sa_data", {})

    # Skip if already enriched
    if sa_data.get("asin") and sa_data.get("buy_box_price"):
        return offer

    # Step 1: Get ASIN
    asin = sa_data.get("asin", "")
    if not asin and upc:
        asins = upc_to_asin(upc)
        if asins:
            asin = asins[0]

    if not asin:
        offer["sa_data"] = {"error": "No ASIN found", "upc": upc}
        return offer

    # Step 2: Get product info
    info = get_product_info(asin)
    if not info:
        offer["sa_data"] = {"asin": asin, "error": "Product not found"}
        return offer

    # Step 3: Extract key data
    prices = info.get("prices", {})
    fees = info.get("fees", {})
    bsr = info.get("bsr", {})
    offers_data = info.get("offers", {})
    competitors = offers_data.get("competitors", {})

    buy_box = float(prices.get("buyBox", {}).get("price") or 0)
    fba_min = float(prices.get("fba", {}).get("minPrice") or 0)
    fba_fee = float(fees.get("fbaFee") or 0)
    referral_fee = float(fees.get("referralFee") or 0)
    referral_rate = fees.get("referralFeeRate") or 0
    storage_fee = float(fees.get("storageFee") or 0)

    # Calculate buyer's profit (based on our wholesale price, or supplier cost if no markup set)
    supplier_unit_cost = offer.get("per_unit_cost") or 0
    wholesale_unit = offer.get("wholesale_price") or 0
    # If no wholesale price set, auto-set a 30% markup over supplier cost
    if not wholesale_unit and supplier_unit_cost > 0:
        wholesale_unit = round(supplier_unit_cost * 1.30, 2)
        offer["wholesale_price"] = wholesale_unit

    total_fees = fba_fee + referral_fee + storage_fee
    # Buyer's profit = what they sell for - what they pay us - Amazon fees
    buyer_profit = buy_box - wholesale_unit - total_fees if buy_box and wholesale_unit else 0
    buyer_roi = (buyer_profit / wholesale_unit * 100) if wholesale_unit > 0 else 0
    # Our margin = what we charge - what we pay supplier
    our_profit = wholesale_unit - supplier_unit_cost if wholesale_unit else 0
    our_margin_pct = (our_profit / wholesale_unit * 100) if wholesale_unit > 0 else 0

    sa_enriched = {
        "asin": asin,
        "title": info.get("title", ""),
        "brand": info.get("brand", ""),
        "product_url": info.get("urls", {}).get("productUrl", ""),
        "image_url": info.get("urls", {}).get("imageUrl", ""),

        # Prices
        "buy_box_price": buy_box,
        "fba_min_price": fba_min,
        "fbm_min_price": float(prices.get("fbm", {}).get("minPrice") or 0),

        # Fees
        "fba_fee": fba_fee,
        "referral_fee": referral_fee,
        "referral_fee_rate": referral_rate,
        "storage_fee": storage_fee,
        "total_fees": round(total_fees, 2),

        # Buyer's profit (if they buy from us and resell on Amazon)
        "buyer_profit": round(buyer_profit, 2),
        "buyer_roi_pct": round(buyer_roi, 1),

        # Our margin
        "our_profit": round(our_profit, 2),
        "our_margin_pct": round(our_margin_pct, 1),

        # Sales & ranking
        "bsr": bsr.get("current"),
        "bsr_top_pct": bsr.get("top"),
        "estimated_monthly_sales": info.get("estimatedSales"),

        # Restriction
        "restriction_status": info.get("restrictionStatus", "UNKNOWN"),

        # Competition
        "fba_sellers": offers_data.get("fbaOffersQty", 0),
        "fbm_sellers": offers_data.get("fbmOffersQty", 0),
        "fba_within_2pct": competitors.get("fbaWithin2Percent", 0),

        # Risk flags
        "is_hazmat": info.get("isHazMat", False),
        "is_meltable": info.get("isMeltable", False),
        "is_oversize": info.get("isOversize", False),
        "is_fragile": info.get("isFragile", False),
        "is_adult": info.get("isAdultProduct", False),

        # Category
        "amazon_category": info.get("category", {}).get("name", ""),

        # Meta
        "enriched_at": time.strftime("%Y-%m-%d %H:%M"),
    }

    offer["sa_data"] = sa_enriched

    # Also update marketplace_data with the more accurate Buy Box price
    mp = offer.setdefault("marketplace_data", {})
    if buy_box > 0:
        mp["amazon_price"] = buy_box
        mp["amazon_source"] = "seller_assistant"

    # Update offer margins
    if buy_box > 0 and wholesale_unit > 0:
        offer["margin_pct"] = round(((buy_box - wholesale_unit) / buy_box) * 100, 1)
    if our_margin_pct:
        offer["our_margin_pct"] = round(our_margin_pct, 1)

    logger.info("Enriched %s: ASIN=%s BBP=$%.2f WS=$%.2f buyer_profit=$%.2f our_profit=$%.2f sales=%s",
                offer.get("product_name", "?")[:30], asin, buy_box, wholesale_unit,
                buyer_profit, our_profit,
                sa_enriched["estimated_monthly_sales"])

    return offer


def bulk_enrich(max_offers=50, delay=1.1):
    """Enrich offers that don't have SA data yet.

    Respects the 60 req/min rate limit (2 calls per product: UPC→ASIN + product info).
    With delay=1.1s between products, we stay under 60 req/min.

    Returns dict with counts.
    """
    offers_path = os.path.join(DATA_DIR, "offers.json")
    try:
        with open(offers_path) as f:
            offers = json.load(f)
    except Exception:
        return {"error": "Could not load offers"}

    enriched = 0
    errors = 0
    restricted = 0
    needs_enrichment = [o for o in offers
                        if o.get("upc")
                        and not o.get("sa_data", {}).get("buy_box_price")
                        and not o.get("sa_data", {}).get("enriched_at")
                        and not o.get("sa_data", {}).get("error")]

    to_process = needs_enrichment[:max_offers]
    logger.info("SA enrichment: %d need enrichment, processing %d",
                len(needs_enrichment), len(to_process))

    for i, offer in enumerate(to_process):
        try:
            enrich_offer(offer)
            sa = offer.get("sa_data", {})
            if sa.get("buy_box_price"):
                enriched += 1
            else:
                errors += 1
            if sa.get("restriction_status") in ("NOT_ELIGIBLE", "APPROVAL_REQUIRED"):
                restricted += 1
        except Exception as e:
            logger.error("Enrichment error: %s", e)
            errors += 1

        if i < len(to_process) - 1:
            time.sleep(delay)

    # Save
    with open(offers_path, "w") as f:
        json.dump(offers, f, indent=2)

    remaining = len(needs_enrichment) - len(to_process)
    logger.info("SA enrichment complete: %d enriched, %d errors, %d restricted, %d remaining",
                enriched, errors, restricted, remaining)

    return {
        "enriched": enriched,
        "errors": errors,
        "restricted": restricted,
        "remaining": remaining,
    }


def _count_unenriched():
    """Return count of offers that need SA enrichment."""
    offers_path = os.path.join(DATA_DIR, "offers.json")
    try:
        with open(offers_path) as f:
            offers = json.load(f)
    except Exception:
        return 0
    return sum(1 for o in offers
               if o.get("upc")
               and not o.get("sa_data", {}).get("buy_box_price")
               and not o.get("sa_data", {}).get("enriched_at")
               and not o.get("sa_data", {}).get("error"))


class EnrichmentPoller:
    """Background thread that checks for unenriched products every interval
    and runs bulk_enrich when any are found."""

    def __init__(self, interval=1800, batch_size=50):
        self.interval = interval  # seconds (default 30 min)
        self.batch_size = batch_size
        self._thread = None
        self._stop_event = threading.Event()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("SA enrichment poller started (every %ds, batch=%d)",
                    self.interval, self.batch_size)

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("SA enrichment poller stopped")

    def _run(self):
        # Initial delay to let app start up
        time.sleep(30)
        while not self._stop_event.is_set():
            try:
                pending = _count_unenriched()
                if pending > 0:
                    logger.info("SA poller: %d unenriched offers found, running enrichment", pending)
                    result = bulk_enrich(max_offers=self.batch_size)
                    logger.info("SA poller result: %s", result)
                else:
                    logger.debug("SA poller: all offers enriched, skipping")
            except Exception as e:
                logger.error("SA poller error: %s", e)
            self._stop_event.wait(self.interval)
