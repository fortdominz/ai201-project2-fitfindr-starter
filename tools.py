"""
tools.py — FitFindr v2

Tools:
    validate_query(user_query)                               → dict
    search_ebay(description, size, max_price, style_goal)    → list[dict]
    suggest_outfit(new_item, wardrobe, style_goal)           → str
    create_fit_card(outfit, new_item)                        → str

eBay credentials required in .env:
    EBAY_CLIENT_ID=...
    EBAY_CLIENT_SECRET=...
"""

import base64
import json
import os
import re
import time

import requests
from dotenv import load_dotenv
from groq import Groq

load_dotenv()


# ── Groq client ────────────────────────────────────────────────────────────────

def _get_groq_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set. Add it to .env.")
    return Groq(api_key=api_key)


# ── eBay OAuth token (module-level cache, 2-hour TTL) ─────────────────────────

_ebay_token_cache: dict = {"token": None, "expires_at": 0.0}


def _get_ebay_token() -> str:
    """Return a valid eBay OAuth bearer token, refreshing when expired."""
    if _ebay_token_cache["token"] and time.time() < _ebay_token_cache["expires_at"]:
        return _ebay_token_cache["token"]

    client_id     = os.environ.get("EBAY_CLIENT_ID")
    client_secret = os.environ.get("EBAY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise ValueError(
            "EBAY_CLIENT_ID and EBAY_CLIENT_SECRET must be set in .env — "
            "register at developer.ebay.com to get them."
        )

    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = requests.post(
        "https://api.ebay.com/identity/v1/oauth2/token",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data="grant_type=client_credentials&scope=https://api.ebay.com/oauth/api_scope",
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    _ebay_token_cache["token"] = data["access_token"]
    # Expire 60s early so we never hand out a token that's about to die
    _ebay_token_cache["expires_at"] = time.time() + data.get("expires_in", 7200) - 60
    return _ebay_token_cache["token"]


# ── eBay result normalizer ─────────────────────────────────────────────────────

def _get_aspect(item: dict, *names: str) -> str | None:
    """Extract the first matching localizedAspect value (case-insensitive)."""
    for name in names:
        for aspect in item.get("localizedAspects", []):
            if aspect.get("name", "").lower() == name.lower():
                return aspect.get("value")
    return None


def _guess_category(category_name: str) -> str:
    n = category_name.lower()
    if any(k in n for k in ("shirt", "tee", "top", "blouse", "sweater", "hoodie", "tank")):
        return "tops"
    if any(k in n for k in ("jeans", "pants", "shorts", "skirt", "trouser", "legging")):
        return "bottoms"
    if any(k in n for k in ("jacket", "coat", "blazer", "outerwear", "vest", "cardigan")):
        return "outerwear"
    if any(k in n for k in ("shoe", "sneaker", "boot", "heel", "sandal", "loafer", "footwear")):
        return "shoes"
    if any(k in n for k in ("bag", "belt", "hat", "scarf", "jewelry", "accessory", "watch", "purse")):
        return "accessories"
    if any(k in n for k in ("dress", "gown", "jumpsuit", "romper")):
        return "dresses"
    return "clothing"


def _normalize_ebay_item(raw: dict) -> dict:
    """Convert an eBay itemSummary dict to FitFindr's internal listing schema."""
    price_info = raw.get("price", {})

    # Thumbnail: Browse API returns thumbnailImages (list) or image (dict)
    images = raw.get("thumbnailImages") or []
    image_url = (
        images[0].get("imageUrl", "") if images
        else raw.get("image", {}).get("imageUrl", "") if raw.get("image")
        else ""
    )

    size  = _get_aspect(raw, "Size", "Size (Women's)", "Size (Men's)", "US Shoe Size")
    color = _get_aspect(raw, "Color", "Main Color")
    brand = _get_aspect(raw, "Brand")
    style = _get_aspect(raw, "Style", "Theme")

    categories   = raw.get("categories", [])
    category_str = categories[0].get("categoryName", "") if categories else ""

    return {
        "id":          raw.get("itemId", ""),
        "title":       raw.get("title", ""),
        "description": raw.get("shortDescription", ""),
        "category":    _guess_category(category_str),
        "style_tags":  [style] if style else [],
        "size":        size or "Not listed",
        "condition":   raw.get("condition", "Used"),
        "price":       float(price_info.get("value", 0)),
        "colors":      [color] if color else [],
        "brand":       brand,
        "platform":    "eBay",
        "image_url":   image_url,
        "item_url":    raw.get("itemWebUrl", ""),
    }


# ── Tool 0: Query validator ────────────────────────────────────────────────────

def validate_query(user_query: str) -> dict:
    """
    Check that the query is relevant to fashion/clothing/style.

    Returns:
        {"valid": bool, "warning": str | None}

    Allows: clothing, shoes, accessories, aesthetics, occasions, or any
    descriptive adjective that relates to personal style — including words
    like "sexy", "edgy", "bold", "flirty".

    Rejects: queries clearly unrelated to fashion (food, tech, academic, etc.).
    Fails open — if the LLM call itself errors, the query is allowed through.
    """
    try:
        prompt = (
            "You are a query guard for FitFindr, a secondhand clothing and style search app.\n\n"
            "ALLOW — return valid=true for:\n"
            "  • Any clothing item, shoe, accessory, or bag\n"
            "  • Style aesthetics (dark academia, cottagecore, y2k, streetwear, grunge, etc.)\n"
            "  • Occasions (date night, office, festival, casual, party, summer)\n"
            "  • Descriptive style adjectives — including 'sexy', 'edgy', 'cute', 'bold',\n"
            "    'flirty', 'cozy', 'elegant', 'romantic', 'fierce', 'quirky', 'minimal'\n"
            "  • Colors, materials, cuts, silhouettes, brands\n"
            "  • Fit preferences (oversized, fitted, cropped, baggy)\n"
            "  • Vague style goals ('I want to look powerful', 'something expressive')\n\n"
            "REJECT — return valid=false ONLY for queries with NO reasonable fashion interpretation:\n"
            "  • Food/cooking, technology/coding, medical/legal/financial advice\n"
            "  • Academic topics (math, science, history)\n"
            "  • Anything clearly not about personal style or clothing\n\n"
            f'Query: "{user_query}"\n\n'
            'Return ONLY valid JSON: {"valid": true_or_false, "reason": "one sentence"}'
        )
        response = _get_groq_client().chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=60,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        data = json.loads(raw)
        if data.get("valid"):
            return {"valid": True, "warning": None}
        return {
            "valid":   False,
            "warning": data.get("reason", "Query doesn't appear to be fashion-related."),
        }
    except Exception:
        return {"valid": True, "warning": None}  # fail open


# ── eBay keyword generator (internal) ─────────────────────────────────────────

def _generate_ebay_keywords(description: str, style_goal: str | None) -> str:
    """
    Translate a natural-language clothing description into tight eBay search
    keywords (2-5 words).
    """
    try:
        style_line = f"\nStyle goal: {style_goal}" if style_goal else ""
        prompt = (
            f"Convert this clothing search into 2-5 eBay search keywords.\n"
            f"Description: {description}{style_line}\n\n"
            "Rules:\n"
            "  • Drop filler: 'looking for', 'something', 'need', 'want', 'I'd like'\n"
            "  • Keep: clothing type, style aesthetic, material, era (vintage, 90s, y2k)\n"
            "  • If a style goal is given, add its most distinctive single keyword\n"
            "  • 2-5 words max — shorter is better for eBay\n\n"
            "Return ONLY the keyword string. No quotes, no explanation.\n"
            "Examples:\n"
            "  'cute floral midi skirt, cottagecore vibes' → floral midi skirt vintage\n"
            "  'something cozy, dark academia' → dark academia wool sweater\n"
            "  'vintage graphic band tee streetwear' → vintage graphic band tee\n"
        )
        response = _get_groq_client().chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=25,
        )
        keywords = response.choices[0].message.content.strip().strip('"\'')
        return keywords if keywords else description
    except Exception:
        return " ".join(description.split()[:4])


# ── Tool 1: search_ebay ───────────────────────────────────────────────────────

def search_ebay(
    description: str,
    size: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    style_goal: str | None = None,
) -> list[dict]:
    """
    Search eBay for real secondhand fashion listings.

    Args:
        description: Natural-language item description.
        size:        Size string to filter by, or None. Applied post-fetch.
        min_price:   Minimum price inclusive, or None.
        max_price:   Maximum price inclusive, or None.
        style_goal:  Optional aesthetic goal to enrich eBay keywords.

    Returns:
        Up to 5 normalized listing dicts. Empty list if nothing matches.

    Raises:
        RuntimeError: if eBay credentials are missing or the API is unreachable.
    """
    keywords = _generate_ebay_keywords(description, style_goal)
    token    = _get_ebay_token()

    filter_parts = [
        "conditions:{LIKE_NEW|VERY_GOOD|GOOD|ACCEPTABLE|USED}",
        "itemLocationCountry:US",
    ]
    if min_price is not None or max_price is not None:
        lo = f"{(min_price or 0):.2f}"
        hi = f"{(max_price or 99999):.2f}"
        filter_parts.append(f"price:[{lo}..{hi}]")
        filter_parts.append("priceCurrency:USD")

    params: dict = {
        "q":            keywords,
        "category_ids": "11450",   # Clothing, Shoes & Accessories
        "filter":       ",".join(filter_parts),
        "limit":        "50",
        "sort":         "bestMatch",
    }

    try:
        resp = requests.get(
            "https://api.ebay.com/buy/browse/v1/item_summary/search",
            headers={
                "Authorization":            f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                "Content-Type":             "application/json",
            },
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.HTTPError as e:
        try:
            body = e.response.json()
        except Exception:
            body = e.response.text
        raise RuntimeError(f"eBay API error {e.response.status_code}: {body}") from e
    except requests.RequestException as e:
        raise RuntimeError(f"eBay API unreachable: {e}") from e

    raw_items  = data.get("itemSummaries", [])
    normalized = [_normalize_ebay_item(item) for item in raw_items]

    # Post-filter by size (aspect filters are unreliable across eBay categories)
    if size:
        user_size = str(size).strip().lower()
        by_size = [
            item for item in normalized
            if item["size"] != "Not listed" and user_size in item["size"].lower()
        ]
        if by_size:
            normalized = by_size

    return normalized


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(
    new_item: dict,
    wardrobe: dict,
    style_goal: str | None = None,
) -> str:
    """
    Suggest 1-2 complete outfit combinations for the found item.

    Args:
        new_item:   Normalized listing dict (the item found on eBay).
        wardrobe:   Wardrobe dict with an 'items' key. May be empty.
        style_goal: Optional aesthetic goal, e.g. "dark academia" or "y2k".

    Returns:
        A non-empty string with outfit suggestions as double-newline-separated
        paragraphs — one paragraph per outfit option.
    """
    try:
        item_summary = (
            f"Item: {new_item['title']}\n"
            f"Category: {new_item['category']}\n"
            f"Colors: {', '.join(new_item.get('colors', [])) or 'not specified'}\n"
            f"Size: {new_item.get('size', 'not listed')}\n"
            f"Condition: {new_item['condition']}\n"
            f"Price: ${new_item['price']:.2f} on {new_item['platform']}"
        )

        style_line = (
            f"\n\nThe user wants to achieve a **{style_goal}** aesthetic — "
            "tailor both outfit options to build toward that look."
            if style_goal else ""
        )

        wardrobe_items = wardrobe.get("items", [])

        if not wardrobe_items:
            prompt = (
                f"A user found this secondhand item:\n{item_summary}{style_line}\n\n"
                "They have no saved wardrobe. Give 1-2 specific outfit ideas for this piece. "
                "Suggest what types of bottoms, shoes, or outerwear pair well. "
                "Describe silhouettes and styling details (how to tuck, layer, roll, cuff, etc.). "
                "Write each outfit as its own paragraph separated by a blank line. "
                "Be specific and casual — like advice from a stylish friend."
            )
        else:
            wardrobe_text = "\n".join(
                f"- {item['name']} ({item['category']}, {', '.join(item['colors'])})"
                + (f" — {item['notes']}" if item.get("notes") else "")
                for item in wardrobe_items
            )
            prompt = (
                f"A user found this secondhand item:\n{item_summary}{style_line}\n\n"
                f"Their wardrobe includes:\n{wardrobe_text}\n\n"
                "Suggest 1-2 complete outfits using the new item and specific pieces from their wardrobe. "
                "Reference wardrobe items by name. Include shoes and outerwear where relevant. "
                "Write each outfit as its own paragraph separated by a blank line. "
                "Be specific about styling details. Casual, direct tone."
            )

        response = _get_groq_client().chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=450,
        )
        result = response.choices[0].message.content.strip()
        return result if result else (
            "This piece has real potential — try pairing it with high-waisted bottoms and clean sneakers."
        )
    except Exception:
        return (
            "Outfit suggestions unavailable right now. "
            "Try pairing this item with similar-toned basics in your wardrobe."
        )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the secondhand find.

    Args:
        outfit:   Outfit suggestion string from suggest_outfit().
        new_item: The normalized listing dict.

    Returns:
        A 2-4 sentence caption string. Returns a safe fallback on empty input.
    """
    if not outfit or not outfit.strip():
        return (
            "Couldn't generate a fit card — outfit suggestion was missing. "
            "Make sure suggest_outfit ran successfully first."
        )

    try:
        prompt = (
            f"Write a 2-4 sentence Instagram/TikTok caption for this thrifted outfit.\n\n"
            f"The item: {new_item['title']} — ${new_item['price']:.2f} from {new_item['platform']}\n"
            f"The outfit: {outfit}\n\n"
            "Requirements:\n"
            "  • Sound like a real person posting their OOTD\n"
            "  • Mention the item name and price naturally — once each\n"
            "  • Capture the specific vibe of this outfit\n"
            "  • Keep it casual and personal\n"
            "  • 2-4 sentences max, no hashtags"
        )

        response = _get_groq_client().chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=150,
        )
        result = response.choices[0].message.content.strip()
        return result if result else "This look is giving everything — and it cost almost nothing."
    except Exception:
        return "This look is giving everything — and it cost almost nothing."
