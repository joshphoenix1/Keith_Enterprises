import json
import base64
import os
import anthropic

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

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


CLAUDE_CREDS_PATH = os.path.expanduser("~/.claude/.credentials.json")


def get_oauth_token():
    """Load Claude Code OAuth access token from ~/.claude/.credentials.json."""
    if os.path.exists(CLAUDE_CREDS_PATH):
        with open(CLAUDE_CREDS_PATH) as f:
            creds = json.load(f)
        oauth = creds.get("claudeAiOauth", {})
        token = oauth.get("accessToken", "")
        if token:
            return token
    return ""


def get_model():
    """Load model preference from accounts.json."""
    accounts_path = os.path.join(DATA_DIR, "accounts.json")
    with open(accounts_path) as f:
        accounts = json.load(f)
    return accounts.get("claude_code", {}).get("model", "claude-sonnet-4-6")


def get_client():
    """Create an Anthropic client using Claude Code OAuth."""
    token = get_oauth_token()
    if not token:
        return None
    return anthropic.Anthropic(api_key=token)


def analyze_image(image_bytes, filename="image.jpg"):
    """Send an image to Claude for product information extraction."""
    client = get_client()
    if not client:
        return {"error": "No Claude Code credentials found. Run 'claude auth' or add an API key in Accounts."}

    # Determine media type
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    media_types = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "gif": "image/gif",
        "webp": "image/webp",
    }
    media_type = media_types.get(ext, "image/jpeg")

    b64_data = base64.standard_b64encode(image_bytes).decode("utf-8")

    model = get_model()

    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": b64_data,
                    },
                },
                {
                    "type": "text",
                    "text": EXTRACTION_PROMPT,
                },
            ],
        }],
    )

    response_text = message.content[0].text.strip()

    # Parse JSON from response (handle markdown code blocks)
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    try:
        result = json.loads(response_text)
        result["_raw_response"] = response_text
        result["_model_used"] = model
        result["_tokens_used"] = {
            "input": message.usage.input_tokens,
            "output": message.usage.output_tokens,
        }
        return result
    except json.JSONDecodeError:
        return {
            "error": "Failed to parse structured data from image",
            "raw_response": response_text,
            "_model_used": model,
        }


def analyze_multiple_images(images):
    """Filter a batch of images, only extract data from actual product images.

    Args:
        images: list of dicts with keys: bytes, filename

    Returns:
        list of dicts — one per image, with is_product flag and extracted data if applicable.
    """
    client = get_client()
    if not client:
        return [{"error": "No Claude Code credentials found. Run 'claude auth' or add an API key in Accounts."}]

    model = get_model()

    # Step 1: Send all images to Claude to classify which are product images
    content_blocks = []
    for i, img in enumerate(images):
        ext = img["filename"].rsplit(".", 1)[-1].lower() if "." in img["filename"] else "jpg"
        media_types = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                       "gif": "image/gif", "webp": "image/webp"}
        media_type = media_types.get(ext, "image/jpeg")
        b64 = base64.standard_b64encode(img["bytes"]).decode("utf-8")

        content_blocks.append({"type": "text", "text": f"Image {i}:"})
        content_blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        })

    content_blocks.append({"type": "text", "text": BATCH_FILTER_PROMPT})

    message = client.messages.create(
        model=model, max_tokens=2048,
        messages=[{"role": "user", "content": content_blocks}],
    )

    response_text = message.content[0].text.strip()
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    try:
        classifications = json.loads(response_text)
    except json.JSONDecodeError:
        # Fallback: treat all as product images
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
