"""WhatsApp integration via lightweight Baileys bridge (self-hosted, open source).

Uses a minimal Node.js/Baileys bridge running in Docker to connect your
personal WhatsApp via QR code scan. All data stays on your server.

Setup:
1. Run: docker compose -f docker-compose.whatsapp.yml up -d
2. Go to Accounts page → WhatsApp section
3. Click "Show QR Code" and scan with your phone (Settings > Linked Devices)
4. Messages start flowing into your Inbox automatically
"""

import json
import os
import logging
import threading
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
INBOX_PATH = os.path.join(DATA_DIR, "inbox.json")
ACCOUNTS_PATH = os.path.join(DATA_DIR, "accounts.json")
ATTACHMENTS_DIR = os.path.join(DATA_DIR, "attachments")

logger = logging.getLogger("keith.whatsapp")

DEFAULT_BRIDGE_URL = "http://localhost:8085"
DEFAULT_API_KEY = "keith-enterprises-wa-key"


def _load_wa_config():
    """Load WhatsApp config from accounts.json."""
    try:
        with open(ACCOUNTS_PATH) as f:
            accounts = json.load(f)
        return accounts.get("whatsapp", {})
    except Exception:
        return {}


def _bridge_url():
    """Get the bridge base URL."""
    config = _load_wa_config()
    return config.get("bridge_url", DEFAULT_BRIDGE_URL).rstrip("/")


def _api_key():
    """Get the bridge API key."""
    config = _load_wa_config()
    return config.get("api_key", DEFAULT_API_KEY)


def _headers():
    """Build request headers for the bridge."""
    return {
        "apikey": _api_key(),
        "Content-Type": "application/json",
    }


def _load_inbox():
    try:
        with open(INBOX_PATH) as f:
            return json.load(f)
    except Exception:
        return {"messages": []}


def _save_inbox(data):
    with open(INBOX_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _next_message_id():
    inbox = _load_inbox()
    messages = inbox.get("messages", [])
    if not messages:
        return 1
    return max(m.get("id", 0) for m in messages) + 1


def _download_local_media(filepath):
    """Read media saved by the bridge to disk.

    The bridge saves downloaded media to its media/ volume. If the path
    is a Docker volume path, we read from the mounted volume.
    """
    try:
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                return f.read(), os.path.basename(filepath)
    except Exception as e:
        logger.error("Failed to read local media %s: %s", filepath, e)
    return None, None


def _download_media(media_url):
    """Download a media file.

    Returns (bytes, filename) or (None, None) on failure.
    """
    import requests

    try:
        resp = requests.get(media_url, timeout=30)
        resp.raise_for_status()
        file_bytes = resp.content

        content_type = resp.headers.get("Content-Type", "image/jpeg")
        ext_map = {
            "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp",
            "image/gif": "gif", "video/mp4": "mp4", "audio/ogg": "ogg",
            "audio/mpeg": "mp3", "application/pdf": "pdf",
        }
        ext = ext_map.get(content_type.split(";")[0].strip(), "bin")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"wa_{ts}.{ext}"

        return file_bytes, filename
    except Exception as e:
        logger.error("Failed to download media: %s", e)
        return None, None


def _save_attachment(file_bytes, filename):
    """Save attachment to data/attachments/ and return the relative path."""
    os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
    filepath = os.path.join(ATTACHMENTS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(file_bytes)
    return f"data/attachments/{filename}"


# ── Bridge API ──

def get_qr_code():
    """Get the QR code for connecting your WhatsApp.

    Returns dict with 'qr' (data:image/png;base64,...) or status info.
    """
    import requests

    try:
        resp = requests.get(f"{_bridge_url()}/qr", headers=_headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Bridge not running. Run: docker compose -f docker-compose.whatsapp.yml up -d"}
    except Exception as e:
        return {"error": str(e)}


def test_connection():
    """Test WhatsApp bridge connection status.

    Returns dict with connection status and details.
    """
    import requests

    url = _bridge_url()

    try:
        resp = requests.get(f"{url}/status", headers=_headers(), timeout=5)
        resp.raise_for_status()
        data = resp.json()
        state = data.get("state", "unknown")

        if state == "connected":
            return {
                "connected": True,
                "state": state,
                "phone_number": data.get("phone", ""),
            }
        elif state == "connecting":
            has_qr = data.get("hasQR", False)
            return {
                "connected": False,
                "state": state,
                "error": "Waiting for QR code scan" if has_qr else "Connecting...",
                "has_qr": has_qr,
            }
        else:
            return {
                "connected": False,
                "state": state,
                "error": "WhatsApp disconnected — scan QR code to reconnect",
            }
    except requests.exceptions.ConnectionError:
        return {
            "connected": False,
            "error": "Bridge not running. Run: docker compose -f docker-compose.whatsapp.yml up -d",
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


# ── Message Processing ──

def process_webhook_payload(payload):
    """Process an incoming Evolution API webhook notification.

    Evolution API sends webhook events for MESSAGES_UPSERT.

    Returns list of processed message dicts (added to inbox).
    """
    processed = []

    # Evolution API webhook format
    event = payload.get("event", "")

    if event != "messages.upsert":
        return processed

    data = payload.get("data", {})

    # Skip outgoing messages (messages we sent)
    if data.get("key", {}).get("fromMe", False):
        return processed

    key = data.get("key", {})
    message = data.get("message", {})
    push_name = data.get("pushName", "")

    remote_jid = key.get("remoteJid", "")
    from_number = remote_jid.replace("@s.whatsapp.net", "").replace("@g.us", "")
    is_group = remote_jid.endswith("@g.us")
    sender_name = push_name or from_number

    # Timestamp
    timestamp = data.get("messageTimestamp")
    try:
        dt = datetime.fromtimestamp(int(timestamp))
        date_str = dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError, OSError):
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    body = ""
    attachments = []

    # Extract message content based on type
    if message.get("conversation"):
        body = message["conversation"]

    elif message.get("extendedTextMessage"):
        body = message["extendedTextMessage"].get("text", "")

    elif message.get("imageMessage"):
        img_msg = message["imageMessage"]
        body = img_msg.get("caption", "Sent an image")

        # Bridge saves media to disk and passes the path
        media_file = data.get("_mediaFile", "")
        media_filename = data.get("_mediaFilename", "")
        if media_file:
            file_bytes, filename = _download_local_media(media_file)
            if file_bytes:
                rel_path = _save_attachment(file_bytes, filename or media_filename)
                attachments.append({
                    "filename": filename or media_filename,
                    "type": "image",
                    "path": rel_path,
                })

        if not body:
            body = "Sent an image"

    elif message.get("documentMessage"):
        doc_msg = message["documentMessage"]
        orig_filename = doc_msg.get("fileName", "document")
        body = doc_msg.get("caption", f"Sent a document: {orig_filename}")

        media_file = data.get("_mediaFile", "")
        if media_file:
            file_bytes, _ = _download_local_media(media_file)
            if file_bytes:
                rel_path = _save_attachment(file_bytes, orig_filename)
                attachments.append({
                    "filename": orig_filename,
                    "type": "document",
                    "path": rel_path,
                })

    elif message.get("videoMessage"):
        body = message["videoMessage"].get("caption", "Sent a video")

    elif message.get("audioMessage"):
        body = "Sent a voice message"

    elif message.get("locationMessage"):
        loc = message["locationMessage"]
        body = f"Shared location: {loc.get('degreesLatitude', '?')}, {loc.get('degreesLongitude', '?')}"
        if loc.get("name"):
            body += f" ({loc['name']})"

    elif message.get("contactMessage"):
        contact = message["contactMessage"]
        body = f"Shared contact: {contact.get('displayName', 'Unknown')}"

    elif message.get("stickerMessage"):
        body = "Sent a sticker"

    else:
        msg_types = [k for k in message.keys() if k != "messageContextInfo"]
        body = f"Received message ({', '.join(msg_types) or 'unknown type'})"

    if not body:
        body = "(empty message)"

    subject = body[:80] + ("..." if len(body) > 80 else "")
    if is_group:
        subject = f"[Group] {subject}"

    inbox_msg = {
        "id": _next_message_id(),
        "source": "whatsapp",
        "from": f"+{from_number}" if not from_number.startswith("+") else from_number,
        "sender_name": sender_name,
        "subject": subject,
        "body": body,
        "date": date_str,
        "read": False,
        "products": [],
        "attachments": attachments,
        "images_scanned": False,
        "wa_message_id": key.get("id", ""),
        "wa_chat_id": remote_jid,
    }

    # Save to inbox
    inbox = _load_inbox()
    inbox["messages"].insert(0, inbox_msg)
    _save_inbox(inbox)

    processed.append(inbox_msg)
    logger.info("Processed WhatsApp message from %s (%s): %s",
                sender_name, from_number, body[:50])

    return processed


# ── Sending Messages ──

def send_message(to_number, text):
    """Send a WhatsApp text message via the bridge.

    Args:
        to_number: Recipient phone number (with country code)
        text: Message text

    Returns dict with success status.
    """
    import requests

    url = f"{_bridge_url()}/send"
    payload = {"to": to_number, "message": text}

    try:
        resp = requests.post(url, headers=_headers(), json=payload, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        logger.info("Sent WhatsApp message to %s: %s", to_number, text[:50])
        return {"success": True, "message_id": result.get("id", "")}
    except Exception as e:
        logger.error("Failed to send WhatsApp message to %s: %s", to_number, e)
        return {"success": False, "error": str(e)}


# ── Auto Processing ──

def _extract_urls(text):
    """Extract URLs from message text."""
    import re
    return re.findall(r'https?://[^\s<>"\']+', text or "")


def _extract_product_from_amazon_url(url):
    """Extract product info from an Amazon URL using the ASIN and Claude CLI.

    Amazon blocks direct scraping, so we extract the ASIN and product name
    from the URL slug, then ask Claude to identify the product.
    """
    import re
    from utils.vision import _claude_call, _parse_json_response

    asin_match = re.search(r'/dp/([A-Z0-9]{10})', url)
    asin = asin_match.group(1) if asin_match else ""

    slug_match = re.search(r'amazon\.[^/]+/([^/]+)/dp/', url)
    slug = slug_match.group(1).replace("-", " ") if slug_match else ""

    if not asin and not slug:
        return {"is_product": False, "error": "Could not extract product info from URL"}

    prompt = f"""I have an Amazon product listing with the following information extracted from the URL:

Product URL slug: {slug}
ASIN: {asin}
Full URL: {url}

Based on this information, identify the product and return a JSON object:

{{
  "is_product": true,
  "product_name": "Full product name (your best guess from the URL slug)",
  "brand": "Brand name",
  "category": "Product category",
  "description": "Brief product description based on what you know about this product",
  "asin": "{asin}",
  "amazon_url": "{url.split('?')[0]}",
  "amazon_category_guess": "Best Amazon category",
  "key_selling_points": ["3-5 marketing angles"],
  "estimated_competition": "Low/Medium/High",
  "notes": "Any relevant details you know about this product"
}}

Only return valid JSON, no other text."""

    try:
        response_text = _claude_call(prompt)
        result = _parse_json_response(response_text)
        result["_source"] = "amazon_url"
        result["_url"] = url
        result["_asin"] = asin
        result["_model_used"] = "claude-cli"
        return result
    except Exception as e:
        return {"is_product": False, "error": f"Claude analysis failed: {e}", "_url": url}


def trigger_auto_process(message_ids=None):
    """Trigger Claude AI auto-processing for new WhatsApp messages.

    Handles both:
    - Image attachments: runs Claude vision to extract product data
    - URLs in message text: fetches the page and extracts product data via Claude
    """
    from utils.vision import (analyze_image, analyze_multiple_images,
                              analyze_url_text, save_scan_result)

    inbox = _load_inbox()
    messages = inbox.get("messages", [])
    processed_count = 0
    products_found = 0

    for msg in messages:
        if msg.get("images_scanned") and msg.get("urls_scanned"):
            continue
        if message_ids and msg["id"] not in message_ids:
            continue

        has_work = False

        # ── Process image attachments ──
        if not msg.get("images_scanned"):
            image_attachments = [a for a in msg.get("attachments", []) if a.get("type") == "image"]
            if image_attachments:
                base_dir = os.path.dirname(os.path.dirname(__file__))
                images = []
                for att in image_attachments:
                    filepath = os.path.join(base_dir, att["path"])
                    if os.path.exists(filepath):
                        with open(filepath, "rb") as f:
                            images.append({"bytes": f.read(), "filename": att["filename"]})

                if images:
                    has_work = True
                    if len(images) == 1:
                        result = analyze_image(images[0]["bytes"], images[0]["filename"])
                        result["filename"] = images[0]["filename"]
                        save_scan_result(result, images[0]["filename"])
                        img_results = [result]
                    else:
                        img_results = analyze_multiple_images(images)
                        for r in img_results:
                            if r.get("is_product") and not r.get("skipped"):
                                save_scan_result(r, r.get("filename", "unknown"))

                    msg["images_scanned"] = True
                    msg.setdefault("scan_results", []).extend(img_results)
                    products_found += sum(1 for r in img_results
                                          if r.get("is_product") and not r.get("skipped"))
            else:
                msg["images_scanned"] = True

        # ── Process URLs in message text ──
        if not msg.get("urls_scanned"):
            urls = _extract_urls(msg.get("body", ""))
            if urls:
                has_work = True
                url_results = []
                for url in urls[:3]:  # Limit to 3 URLs per message
                    try:
                        # Try direct page fetch first
                        result = analyze_url_text(url)
                        if result.get("error") and "amazon" in url.lower():
                            # Amazon blocks scraping — use ASIN extraction + Claude
                            logger.info("Direct fetch failed for Amazon URL, using ASIN extraction: %s", url[:60])
                            result = _extract_product_from_amazon_url(url)

                        if result.get("is_product"):
                            result["_source"] = "url"
                            result["_url"] = url
                            save_scan_result(result, url)
                            url_results.append(result)
                            products_found += 1
                            logger.info("Extracted product from URL: %s — %s",
                                        url[:60], result.get("product_name", "?"))
                        elif result.get("error"):
                            url_results.append({"url": url, "error": result["error"], "is_product": False})
                            logger.warning("URL extraction failed for %s: %s", url[:60], result["error"])
                        else:
                            url_results.append(result)
                    except Exception as e:
                        logger.error("URL processing error for %s: %s", url[:60], e)
                        url_results.append({"url": url, "error": str(e), "is_product": False})

                msg["urls_scanned"] = True
                msg.setdefault("scan_results", []).extend(url_results)
            else:
                msg["urls_scanned"] = True

        if has_work:
            processed_count += 1

    if processed_count > 0:
        _save_inbox(inbox)

    logger.info("Auto-processed %d WhatsApp messages, found %d products",
                processed_count, products_found)

    return {"processed": processed_count, "products_found": products_found}
