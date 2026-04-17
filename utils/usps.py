"""Address verification via OpenStreetMap Nominatim (no API key required)."""

import json
import logging
import urllib.request
import urllib.parse

log = logging.getLogger("keith.address")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def verify_address(line1, line2="", city="", state="", zip5=""):
    """Verify and standardize a US address via OpenStreetMap Nominatim.

    Returns dict with:
        verified: bool
        address: standardized address dict
        error: error message if not verified
        original: the input address
    """
    original = {"line1": line1, "line2": line2, "city": city, "state": state, "zip": zip5}

    # Build query string
    parts = [p for p in [line1, line2, city, state, zip5] if p and p.strip()]
    if not parts:
        return {"verified": False, "error": "No address provided", "original": original}

    query = ", ".join(parts)

    params = urllib.parse.urlencode({
        "q": query,
        "format": "jsonv2",
        "addressdetails": 1,
        "countrycodes": "us",
        "limit": 1,
    })
    url = f"{NOMINATIM_URL}?{params}"

    req = urllib.request.Request(url, headers={
        "User-Agent": "KeithEnterprisesApp/1.0",
        "Accept": "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log.error("Nominatim request failed: %s", e)
        return {"verified": False, "error": f"Address lookup failed: {e}", "original": original}

    if not data:
        return {"verified": False, "error": "Address not found", "original": original}

    result = data[0]
    addr = result.get("address", {})

    # Extract standardized components
    house_number = addr.get("house_number", "")
    road = addr.get("road", "")
    std_line1 = f"{house_number} {road}".strip() if house_number or road else line1

    std_city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("hamlet") or city
    std_state = addr.get("state", state)
    std_zip = addr.get("postcode", zip5)

    # Convert full state name to abbreviation
    std_state_abbr = _state_abbr(std_state) or std_state

    # Confidence check — Nominatim importance score
    importance = float(result.get("importance", 0))
    place_rank = int(result.get("place_rank", 0))
    # place_rank >= 26 means building/address level match
    is_address_level = place_rank >= 26

    return {
        "verified": is_address_level,
        "confidence": round(importance, 3),
        "place_rank": place_rank,
        "display_name": result.get("display_name", ""),
        "address": {
            "line1": std_line1.upper(),
            "line2": (line2 or "").upper(),
            "city": std_city.upper(),
            "state": std_state_abbr.upper(),
            "zip5": std_zip.split("-")[0] if std_zip else "",
            "zip4": std_zip.split("-")[1] if "-" in (std_zip or "") else "",
            "zip_full": std_zip or "",
        },
        "original": original,
    }


_STATE_MAP = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC",
}


def _state_abbr(name):
    """Convert full state name to 2-letter abbreviation."""
    if not name:
        return ""
    if len(name) <= 2:
        return name.upper()
    return _STATE_MAP.get(name, _STATE_MAP.get(name.title(), ""))
