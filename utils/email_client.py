"""Email ingestion via IMAP — polls Gmail for new supplier offers.

Fetches unread emails, extracts body + image attachments, saves to inbox.json,
and optionally triggers Claude AI auto-processing for images/URLs.
"""

import imaplib
import email
from email.header import decode_header
import json
import os
import logging
import threading
import time
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
INBOX_PATH = os.path.join(DATA_DIR, "inbox.json")
ACCOUNTS_PATH = os.path.join(DATA_DIR, "accounts.json")
ATTACHMENTS_DIR = os.path.join(DATA_DIR, "attachments")

logger = logging.getLogger("keith.email")

# Track which email UIDs we've already processed (persisted to disk)
SEEN_PATH = os.path.join(DATA_DIR, "email_seen_uids.json")

# Senders to skip — automated/system emails that aren't supplier offers
SKIP_SENDERS = {
    "no-reply@accounts.google.com",
    "noreply@google.com",
    "no-reply@google.com",
    "mailer-daemon@google.com",
    "mailer-daemon@googlemail.com",
    "notifications@github.com",
    "noreply@github.com",
}


def _load_email_config():
    try:
        with open(ACCOUNTS_PATH) as f:
            accounts = json.load(f)
        return accounts.get("email", {})
    except Exception:
        return {}


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


def _load_seen_uids():
    try:
        with open(SEEN_PATH) as f:
            return set(json.load(f))
    except Exception:
        return set()


def _save_seen_uids(uids):
    with open(SEEN_PATH, "w") as f:
        json.dump(list(uids), f)


def _save_attachment(file_bytes, filename):
    os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
    # Sanitize filename — preserve extension
    base, ext = os.path.splitext(filename)
    safe_base = "".join(c for c in base if c.isalnum() or c in "._- ")[:80]
    safe_name = safe_base + ext
    if not safe_name or safe_name == ext:
        safe_name = f"email_attach_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    filepath = os.path.join(ATTACHMENTS_DIR, safe_name)
    # Avoid overwriting
    if os.path.exists(filepath):
        base, ext = os.path.splitext(safe_name)
        safe_name = f"{base}_{datetime.now().strftime('%H%M%S')}{ext}"
        filepath = os.path.join(ATTACHMENTS_DIR, safe_name)
    with open(filepath, "wb") as f:
        f.write(file_bytes)
    return f"data/attachments/{safe_name}", safe_name


def _decode_header_value(value):
    if value is None:
        return ""
    decoded_parts = decode_header(value)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result)


def _get_body(msg):
    """Extract plain text body from email message."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/plain" and "attachment" not in disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body += payload.decode(charset, errors="replace")
            elif content_type == "text/html" and not body and "attachment" not in disposition:
                # Fallback to HTML if no plain text
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html_text = payload.decode(charset, errors="replace")
                    # Strip HTML tags (basic)
                    import re
                    body = re.sub(r'<[^>]+>', ' ', html_text)
                    body = re.sub(r'\s+', ' ', body).strip()
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
    return body.strip()


def _get_attachments(msg):
    """Extract image attachments from email."""
    attachments = []
    image_types = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp"}

    spreadsheet_types = {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "application/octet-stream",  # sometimes xlsx comes as this
    }
    spreadsheet_exts = {".xlsx", ".xls", ".csv"}

    if not msg.is_multipart():
        return attachments

    for part in msg.walk():
        content_type = part.get_content_type()
        disposition = str(part.get("Content-Disposition", ""))
        filename = part.get_filename()
        if filename:
            filename = _decode_header_value(filename)

        # Get images — either as attachments or inline
        if content_type in image_types:
            payload = part.get_payload(decode=True)
            if not payload or len(payload) < 1000:
                continue  # Skip tiny images (tracking pixels, etc)

            if not filename:
                ext = content_type.split("/")[-1]
                if ext == "jpeg":
                    ext = "jpg"
                filename = f"email_img_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"

            rel_path, saved_name = _save_attachment(payload, filename)
            attachments.append({
                "filename": saved_name,
                "type": "image",
                "path": rel_path,
            })

        # Get spreadsheets (xlsx, xls, csv)
        elif (content_type in spreadsheet_types or
              (filename and os.path.splitext(filename)[1].lower() in spreadsheet_exts)):
            payload = part.get_payload(decode=True)
            if not payload:
                continue

            if not filename:
                filename = f"offer_sheet_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

            rel_path, saved_name = _save_attachment(payload, filename)
            attachments.append({
                "filename": saved_name,
                "type": "spreadsheet",
                "path": rel_path,
            })

    return attachments


def test_connection():
    """Test IMAP connection with stored credentials. Returns status dict."""
    config = _load_email_config()

    if not config.get("enabled"):
        return {"connected": False, "error": "Email not enabled in Accounts settings"}

    address = config.get("email_address", "")
    password = config.get("password", "")

    if not address or not password:
        return {"connected": False, "error": "Email address or app password not configured"}

    # Determine IMAP server from provider
    provider = config.get("provider", "Gmail")
    imap_server = "imap.gmail.com"
    if "outlook" in provider.lower() or "hotmail" in address.lower():
        imap_server = "outlook.office365.com"
    elif "yahoo" in provider.lower() or "yahoo" in address.lower():
        imap_server = "imap.mail.yahoo.com"

    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(address, password)
        status, folders = mail.list()
        mail.select("INBOX", readonly=True)
        status, msgs = mail.search(None, "ALL")
        total = len(msgs[0].split()) if msgs[0] else 0
        mail.logout()
        return {
            "connected": True,
            "server": imap_server,
            "email": address,
            "total_emails": total,
        }
    except imaplib.IMAP4.error as e:
        return {"connected": False, "error": f"IMAP auth failed: {e}"}
    except Exception as e:
        return {"connected": False, "error": str(e)}


def fetch_new_emails(max_emails=10):
    """Fetch unread emails via IMAP and add to inbox.

    Returns list of processed inbox message dicts.
    """
    config = _load_email_config()

    if not config.get("enabled"):
        return []

    address = config.get("email_address", "")
    password = config.get("password", "")
    if not address or not password:
        return []

    provider = config.get("provider", "Gmail")
    imap_server = "imap.gmail.com"
    if "outlook" in provider.lower() or "hotmail" in address.lower():
        imap_server = "outlook.office365.com"
    elif "yahoo" in provider.lower() or "yahoo" in address.lower():
        imap_server = "imap.mail.yahoo.com"

    seen_uids = _load_seen_uids()
    processed = []

    try:
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(address, password)
        mail.select("INBOX", readonly=True)

        # Search for unseen emails
        status, msg_nums = mail.search(None, "UNSEEN")
        if status != "OK" or not msg_nums[0]:
            mail.logout()
            logger.info("No new unread emails found")
            return []

        email_ids = msg_nums[0].split()
        # Process most recent first, limit count
        email_ids = email_ids[-max_emails:]

        for eid in email_ids:
            uid_resp = mail.fetch(eid, "(UID)")
            if uid_resp[0] != "OK":
                continue
            # Parse UID from response like b'1 (UID 12345)'
            uid_str = uid_resp[1][0].decode()
            uid = uid_str.split("UID")[1].strip().rstrip(")")
            if uid in seen_uids:
                continue

            status, msg_data = mail.fetch(eid, "(RFC822)")
            if status != "OK":
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            # Parse headers
            from_addr = _decode_header_value(msg.get("From", ""))
            subject = _decode_header_value(msg.get("Subject", "(No Subject)"))
            date_str = msg.get("Date", "")

            # Parse sender name and email
            sender_name = from_addr
            sender_email = from_addr
            if "<" in from_addr:
                parts = from_addr.split("<")
                sender_name = parts[0].strip().strip('"')
                sender_email = parts[1].rstrip(">").strip()

            # Skip known non-supplier senders
            if sender_email.lower() in SKIP_SENDERS:
                seen_uids.add(uid)
                logger.debug("Skipped system email from %s", sender_email)
                continue

            # Parse date
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(date_str)
                formatted_date = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                formatted_date = datetime.now().strftime("%Y-%m-%d %H:%M")

            body = _get_body(msg)
            attachments = _get_attachments(msg)

            inbox_msg = {
                "id": _next_message_id(),
                "source": "email",
                "from": sender_email,
                "sender_name": sender_name or sender_email,
                "subject": subject[:120],
                "body": body[:5000],  # Limit body size
                "date": formatted_date,
                "read": False,
                "products": [],
                "attachments": attachments,
                "images_scanned": False,
                "urls_scanned": False,
                "email_uid": uid,
            }

            # Save to inbox
            inbox = _load_inbox()
            inbox["messages"].insert(0, inbox_msg)
            _save_inbox(inbox)

            seen_uids.add(uid)
            processed.append(inbox_msg)

            logger.info("Ingested email from %s: %s (%d attachments)",
                        sender_email, subject[:50], len(attachments))

        _save_seen_uids(seen_uids)
        mail.logout()

    except imaplib.IMAP4.error as e:
        logger.error("IMAP error: %s", e)
    except Exception as e:
        logger.error("Email fetch error: %s", e)

    return processed


def fetch_and_process():
    """Fetch new emails and trigger AI auto-processing (images, URLs, and body text)."""
    import re

    new_msgs = fetch_new_emails()
    if not new_msgs:
        return {"fetched": 0, "processed": 0}

    products_found = 0

    try:
        from utils.vision import (analyze_image, analyze_multiple_images,
                                  analyze_url_text, analyze_email_body, save_scan_result)

        inbox = _load_inbox()
        messages = inbox.get("messages", [])
        new_ids = {m["id"] for m in new_msgs}

        for msg in messages:
            if msg["id"] not in new_ids:
                continue

            msg.setdefault("scan_results", [])

            # Process image attachments
            image_attachments = [a for a in msg.get("attachments", []) if a.get("type") == "image"]
            if image_attachments and not msg.get("images_scanned"):
                base_dir = os.path.dirname(os.path.dirname(__file__))
                images = []
                for att in image_attachments:
                    filepath = os.path.join(base_dir, att["path"])
                    if os.path.exists(filepath):
                        with open(filepath, "rb") as f:
                            images.append({"bytes": f.read(), "filename": att["filename"]})

                if images:
                    if len(images) == 1:
                        result = analyze_image(images[0]["bytes"], images[0]["filename"])
                        result["filename"] = images[0]["filename"]
                        save_scan_result(result, images[0]["filename"])
                        msg["scan_results"].append(result)
                    else:
                        results = analyze_multiple_images(images)
                        for r in results:
                            if r.get("is_product") and not r.get("skipped"):
                                save_scan_result(r, r.get("filename", "unknown"))
                        msg["scan_results"].extend(results)
                msg["images_scanned"] = True

            # Process URLs in body
            if not msg.get("urls_scanned"):
                urls = re.findall(r'https?://[^\s<>"\']+', msg.get("body", "") or "")
                for url in urls[:3]:
                    try:
                        result = analyze_url_text(url)
                        if result.get("is_product"):
                            result["_source"] = "url"
                            result["_url"] = url
                            save_scan_result(result, url)
                            msg["scan_results"].append(result)
                    except Exception as e:
                        logger.error("URL processing error: %s", e)
                msg["urls_scanned"] = True

            # Process spreadsheet attachments
            if not msg.get("sheets_scanned"):
                sheet_attachments = [a for a in msg.get("attachments", [])
                                     if a.get("type") == "spreadsheet"]
                if sheet_attachments:
                    base_dir = os.path.dirname(os.path.dirname(__file__))
                    for att in sheet_attachments:
                        filepath = os.path.join(base_dir, att["path"])
                        if os.path.exists(filepath):
                            sheet_products = analyze_spreadsheet(
                                filepath,
                                sender=msg.get("sender_name", ""),
                                subject=msg.get("subject", ""),
                            )
                            for p in sheet_products:
                                save_scan_result(p, att["filename"])
                            msg["scan_results"].extend(sheet_products)
                msg["sheets_scanned"] = True

            # Process email body text with Claude (fallback if no sheets/images)
            if (not msg.get("text_scanned") and msg.get("body", "").strip()
                    and not msg.get("scan_results")):
                body = msg["body"]
                if len(body) > 100:
                    text_products = analyze_email_body(
                        body,
                        sender=msg.get("sender_name", ""),
                        subject=msg.get("subject", ""),
                    )
                    for p in text_products:
                        save_scan_result(p, f"email_{msg['id']}")
                    msg["scan_results"].extend(text_products)
                msg["text_scanned"] = True

            products_found += sum(1 for r in msg["scan_results"]
                                  if r.get("is_product") and not r.get("skipped"))

        _save_inbox(inbox)
    except Exception as e:
        logger.error("Auto-process error for emails: %s", e)

    logger.info("Email fetch complete: %d new, %d products found", len(new_msgs), products_found)
    return {"fetched": len(new_msgs), "processed": len(new_msgs), "products_found": products_found}


class EmailPoller:
    """Background thread that polls for new emails on an interval."""

    def __init__(self, interval=120):
        self.interval = interval  # seconds between polls
        self._thread = None
        self._stop_event = threading.Event()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Email poller started (every %ds)", self.interval)

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Email poller stopped")

    def _run(self):
        # Initial delay to let app start up
        time.sleep(10)
        while not self._stop_event.is_set():
            try:
                config = _load_email_config()
                if config.get("enabled"):
                    fetch_and_process()
            except Exception as e:
                logger.error("Email poll error: %s", e)
            self._stop_event.wait(self.interval)
