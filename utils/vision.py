import json
import base64
import os
import subprocess
import tempfile
import time as _time
import logging

logger = logging.getLogger("keith.vision")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

EXTRACTION_PROMPT = """First, determine if this image shows an actual product — a product label, packaging, bottle, box, listing screenshot, spec sheet, or physical item being offered for sale.

If this is NOT a product image (e.g. a signature, logo, banner, profile photo, shipping label, invoice, generic graphic, or unrelated image), return:
{"is_product": false, "reason": "Brief explanation of what the image shows instead"}

If this IS a product image, analyze it and extract all product information you can find. Return a JSON object:

{
  "is_product": true,
  "product_name": "Full product name",
  "brand": "Brand name",
  "category": "Product category (e.g. Health & Household, Kitchen & Dining, Sports & Outdoors)",
  "description": "Brief product description",
  "ingredients": ["list of ingredients if visible"],
  "nutrition_facts": {"serving_size": "", "calories": "", "other": {}},
  "net_weight": "Weight/volume with units",
  "upc_barcode": "UPC/EAN if visible",
  "claims": ["organic", "non-gmo", "vegan", etc.],
  "warnings": ["any warnings or allergen info"],
  "manufacturer": "Manufacturer name and location if visible",
  "suggested_retail_price": null,
  "amazon_category_guess": "Best Amazon category for this product",
  "key_selling_points": ["list of 3-5 marketing angles for Amazon listing"],
  "estimated_competition": "Low/Medium/High based on product type",
  "notes": "Any other relevant details extracted from the image"
}

Only return valid JSON, no other text."""


BATCH_FILTER_PROMPT = """You are reviewing multiple images from an email or message that contains a product offer. Your job is to identify which images show actual products being offered for sale, and which are non-product images (logos, signatures, banners, profile photos, shipping labels, invoices, decorative graphics, etc.).

For each image, respond with a JSON array. Each entry should be:
{"index": 0, "is_product": true/false, "reason": "what the image shows"}

Only return valid JSON array, no other text."""


URL_PAGE_EXTRACTION_PROMPT = """Analyze the following webpage content and extract all product information you can find. This is text scraped from a product page (e.g. Amazon listing, Alibaba product page, supplier website, etc.).

Return a JSON object:

{
  "is_product": true,
  "product_name": "Full product name",
  "brand": "Brand name",
  "category": "Product category (e.g. Health & Household, Kitchen & Dining, Sports & Outdoors)",
  "description": "Brief product description",
  "ingredients": ["list of ingredients if visible"],
  "nutrition_facts": {"serving_size": "", "calories": "", "other": {}},
  "net_weight": "Weight/volume with units",
  "upc_barcode": "UPC/EAN if visible",
  "claims": ["organic", "non-gmo", "vegan", etc.],
  "warnings": ["any warnings or allergen info"],
  "manufacturer": "Manufacturer name and location if visible",
  "suggested_retail_price": "Price if listed",
  "amazon_category_guess": "Best Amazon category for this product",
  "key_selling_points": ["list of 3-5 marketing angles for Amazon listing"],
  "estimated_competition": "Low/Medium/High based on product type",
  "notes": "Any other relevant details extracted from the page"
}

If this page does NOT contain product information, return:
{"is_product": false, "reason": "Brief explanation of what the page shows instead"}

Only return valid JSON, no other text."""


URL_IMAGE_EXTRACTION_PROMPT = """I'm going to show you images scraped from a product page. Analyze ONLY the images that show actual products — labels, packaging, bottles, boxes, listings, or physical items.

Skip any images that are: icons, logos, UI elements, banners, navigation graphics, avatars, or unrelated images.

For each product image found, extract all product information. Return a JSON object:

{
  "is_product": true,
  "product_name": "Full product name",
  "brand": "Brand name",
  "category": "Product category (e.g. Health & Household, Kitchen & Dining, Sports & Outdoors)",
  "description": "Brief product description",
  "ingredients": ["list of ingredients if visible"],
  "nutrition_facts": {"serving_size": "", "calories": "", "other": {}},
  "net_weight": "Weight/volume with units",
  "upc_barcode": "UPC/EAN if visible",
  "claims": ["organic", "non-gmo", "vegan", etc.],
  "warnings": ["any warnings or allergen info"],
  "manufacturer": "Manufacturer name and location if visible",
  "suggested_retail_price": null,
  "amazon_category_guess": "Best Amazon category for this product",
  "key_selling_points": ["list of 3-5 marketing angles for Amazon listing"],
  "estimated_competition": "Low/Medium/High based on product type",
  "notes": "Any other relevant details extracted from the images"
}

If none of the images show products, return:
{"is_product": false, "reason": "No product images found on the page"}

Only return valid JSON, no other text."""


# ── Claude CLI interface ──

CLAUDE_CREDS_PATH = os.path.expanduser("~/.claude/.credentials.json")

# Cache for validated token
_token_cache = {"validated": False, "last_check": 0}
_TOKEN_CHECK_INTERVAL = 300


def _claude_call(prompt, image_paths=None, timeout=120):
    """Call Claude via the CLI (`claude -p`). Returns response text.

    For image analysis, pass image_paths — the CLI will read them via its Read tool.
    """
    cmd = ["claude", "-p", "--output-format", "text"]

    if image_paths:
        cmd.extend(["--allowedTools", "Read", "--add-dir", BASE_DIR])
        # Prepend read instructions for each image
        read_lines = []
        for i, path in enumerate(image_paths):
            read_lines.append(f"Read the image file at {path}")
        prompt = "\n".join(read_lines) + "\n\nNow analyze the images above.\n\n" + prompt

    result = subprocess.run(
        cmd, input=prompt, capture_output=True, text=True, timeout=timeout
    )

    if result.returncode != 0:
        error_msg = result.stderr.strip() or "Unknown CLI error"
        logger.error("Claude CLI error (rc=%d): %s", result.returncode, error_msg[:200])
        raise RuntimeError(f"Claude CLI error: {error_msg}")

    return result.stdout.strip()


def _parse_json_response(response_text):
    """Parse JSON from Claude response, handling markdown code blocks."""
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])
    return json.loads(text)


def get_model():
    """Return the model used for AI calls (for display/logging)."""
    return "claude-cli"


def validate_token(token=None):
    """Check if the Claude CLI is available and authenticated."""
    now = _time.time()
    if (_token_cache["validated"] and
            now - _token_cache["last_check"] < _TOKEN_CHECK_INTERVAL):
        return {"valid": True}

    # Check CLI binary exists
    cli_path = subprocess.run(["which", "claude"], capture_output=True, text=True)
    if cli_path.returncode != 0:
        return {"valid": False, "error": "Claude CLI not found. Install it with: npm install -g @anthropic-ai/claude-code"}

    # Check credentials file and expiry
    if os.path.exists(CLAUDE_CREDS_PATH):
        try:
            with open(CLAUDE_CREDS_PATH) as f:
                creds = json.load(f)
            expires_at = creds.get("claudeAiOauth", {}).get("expiresAt", 0)
            now_ms = int(_time.time() * 1000)
            if expires_at > now_ms:
                _token_cache["validated"] = True
                _token_cache["last_check"] = now
                return {"valid": True}
            else:
                _token_cache["validated"] = False
                return {"valid": False, "error": "Claude CLI token expired. Run 'claude auth' to refresh."}
        except (json.JSONDecodeError, IOError):
            pass

    return {"valid": False, "error": "No Claude CLI credentials found. Run 'claude auth' to connect."}


# Keep for backward compat with health check page
def get_oauth_token():
    """Check if OAuth credentials exist."""
    if os.path.exists(CLAUDE_CREDS_PATH):
        try:
            with open(CLAUDE_CREDS_PATH) as f:
                creds = json.load(f)
            return creds.get("claudeAiOauth", {}).get("accessToken", "")
        except (json.JSONDecodeError, IOError):
            pass
    return ""


def get_client():
    """Backward compat — returns truthy if CLI is available."""
    return validate_token().get("valid", False)


# ── Image analysis ──

def analyze_image(image_bytes, filename="image.jpg"):
    """Send an image to Claude CLI for product information extraction."""
    # Save image to temp file
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False, dir=DATA_DIR) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    try:
        response_text = _claude_call(EXTRACTION_PROMPT, image_paths=[tmp_path])
        result = _parse_json_response(response_text)
        result["_raw_response"] = response_text
        result["_model_used"] = "claude-cli"
        return result
    except json.JSONDecodeError:
        return {
            "error": "Failed to parse structured data from image",
            "raw_response": response_text,
            "_model_used": "claude-cli",
        }
    except Exception as e:
        return {"error": f"Image analysis failed: {e}", "_model_used": "claude-cli"}
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def analyze_multiple_images(images):
    """Filter a batch of images, only extract data from actual product images.

    Args:
        images: list of dicts with keys: bytes, filename

    Returns:
        list of dicts — one per image, with is_product flag and extracted data if applicable.
    """
    # Save all images to temp files
    tmp_paths = []
    try:
        for img in images:
            ext = img["filename"].rsplit(".", 1)[-1].lower() if "." in img["filename"] else "jpg"
            with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False, dir=DATA_DIR) as tmp:
                tmp.write(img["bytes"])
                tmp_paths.append(tmp.name)

        # Step 1: Classify which images are products
        classify_prompt = ""
        for i, path in enumerate(tmp_paths):
            classify_prompt += f"Image {i} is at: {path}\n"
        classify_prompt += "\n" + BATCH_FILTER_PROMPT

        response_text = _claude_call(classify_prompt, image_paths=tmp_paths)
        try:
            classifications = _parse_json_response(response_text)
        except json.JSONDecodeError:
            classifications = [{"index": i, "is_product": True, "reason": "classification failed"}
                              for i in range(len(images))]

        # Step 2: For each product image, run full extraction
        results = []
        for cls in classifications:
            idx = cls.get("index", 0)
            if idx >= len(images):
                continue
            img = images[idx]

            if not cls.get("is_product", False):
                results.append({
                    "filename": img["filename"],
                    "is_product": False,
                    "reason": cls.get("reason", "Not a product image"),
                    "skipped": True,
                })
            else:
                extracted = analyze_image(img["bytes"], img["filename"])
                extracted["is_product"] = True
                extracted["filename"] = img["filename"]
                results.append(extracted)

        return results
    finally:
        for path in tmp_paths:
            try:
                os.unlink(path)
            except OSError:
                pass


# ── URL analysis ──

def fetch_url(url):
    """Fetch a URL and return the page text content and image URLs."""
    import requests as _requests
    import re

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }
    try:
        session = _requests.Session()
        resp = session.get(url, headers=headers, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        html_text = resp.text
        if ("Just a moment" in html_text[:1000] and "cloudflare" in html_text.lower()[:5000]) or \
           ("Checking your browser" in html_text[:1000]):
            return {"error": "This site uses Cloudflare bot protection and cannot be scraped directly."}
    except _requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 403:
            return {"error": "403 Forbidden — this site blocks automated access."}
        return {"error": f"Failed to fetch URL: {str(e)}"}
    except Exception as e:
        return {"error": f"Failed to fetch URL: {str(e)}"}

    text = re.sub(r"<script[^>]*>.*?</script>", "", html_text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    img_urls = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html_text, re.IGNORECASE)
    img_urls += re.findall(r'<img[^>]+data-src=["\']([^"\']+)["\']', html_text, re.IGNORECASE)

    from urllib.parse import urljoin
    img_urls = [urljoin(url, u) for u in img_urls]

    skip_patterns = ["1x1", "pixel", "tracking", "spacer", "blank", "favicon", ".svg",
                     "sprite", "icon-", "loading", "spinner", "badge"]
    filtered = []
    for u in img_urls:
        lower = u.lower()
        if any(p in lower for p in skip_patterns):
            continue
        if lower.endswith((".js", ".css")):
            continue
        filtered.append(u)

    seen = set()
    unique = []
    for u in filtered:
        if u not in seen:
            seen.add(u)
            unique.append(u)

    return {"text": text[:50000], "images": unique[:20], "full_url": url}


def analyze_url_text(url):
    """Fetch a URL and extract product info from the page text via Claude CLI."""
    fetched = fetch_url(url)
    if "error" in fetched:
        return fetched

    page_text = fetched["text"]
    prompt = f"URL: {url}\n\nPage content:\n{page_text}\n\n{URL_PAGE_EXTRACTION_PROMPT}"

    try:
        response_text = _claude_call(prompt)
        result = _parse_json_response(response_text)
        result["_raw_response"] = response_text
        result["_model_used"] = "claude-cli"
        result["_source_url"] = url
        result["_extraction_mode"] = "page_text"
        return result
    except json.JSONDecodeError:
        return {"error": "Failed to parse structured data from page",
                "raw_response": response_text, "_model_used": "claude-cli"}
    except Exception as e:
        return {"error": f"URL analysis failed: {e}", "_model_used": "claude-cli"}


def analyze_url_images(url):
    """Fetch a URL, download product images, and extract product info via Claude CLI."""
    import requests as _requests

    fetched = fetch_url(url)
    if "error" in fetched:
        return fetched

    img_urls = fetched.get("images", [])
    if not img_urls:
        return {"error": "No images found on the page.", "_source_url": url}

    img_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": url,
    }

    tmp_paths = []
    try:
        for img_url in img_urls[:10]:
            try:
                resp = _requests.get(img_url, headers=img_headers, timeout=15, allow_redirects=True)
                resp.raise_for_status()
                content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
                if not content_type.startswith("image/"):
                    continue
                ext = content_type.split("/")[1].replace("jpeg", "jpg")
                with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False, dir=DATA_DIR) as tmp:
                    tmp.write(resp.content)
                    tmp_paths.append(tmp.name)
            except Exception:
                continue

        if not tmp_paths:
            return {"error": "Could not download any images from the page.", "_source_url": url}

        response_text = _claude_call(URL_IMAGE_EXTRACTION_PROMPT, image_paths=tmp_paths)
        result = _parse_json_response(response_text)
        result["_raw_response"] = response_text
        result["_model_used"] = "claude-cli"
        result["_source_url"] = url
        result["_extraction_mode"] = "page_images"
        result["_images_downloaded"] = len(tmp_paths)
        return result
    except json.JSONDecodeError:
        return {"error": "Failed to parse structured data from images",
                "raw_response": response_text, "_model_used": "claude-cli"}
    except Exception as e:
        return {"error": f"URL image analysis failed: {e}", "_model_used": "claude-cli"}
    finally:
        for path in tmp_paths:
            try:
                os.unlink(path)
            except OSError:
                pass


# ── Scan storage ──

def save_scan_result(result, filename):
    """Save a scan result to the scans log."""
    scans_path = os.path.join(DATA_DIR, "scans.json")
    if os.path.exists(scans_path):
        with open(scans_path) as f:
            scans = json.load(f)
    else:
        scans = []

    from datetime import datetime
    entry = {
        "id": len(scans) + 1,
        "filename": filename,
        "timestamp": datetime.now().isoformat(),
        "data": result,
    }
    scans.append(entry)

    with open(scans_path, "w") as f:
        json.dump(scans, f, indent=2)

    return entry


def load_scans():
    """Load all scan results."""
    scans_path = os.path.join(DATA_DIR, "scans.json")
    if os.path.exists(scans_path):
        with open(scans_path) as f:
            return json.load(f)
    return []
