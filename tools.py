"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()

    # Filter by price and size first (cheap operations before scoring)
    if max_price is not None:
        listings = [l for l in listings if l["price"] <= max_price]
    if size is not None:
        size_lower = size.strip().lower()
        listings = [l for l in listings if size_lower in l["size"].lower()]

    # Score by keyword overlap across title (3 pts), style_tags (2 pts), description (1 pt)
    keywords = [w.lower() for w in description.split() if w]

    scored = []
    for listing in listings:
        title_words = listing["title"].lower().split()
        tags = [t.lower() for t in listing["style_tags"]]
        desc_words = listing["description"].lower().split()

        score = 0
        for kw in keywords:
            score += 3 * sum(1 for w in title_words if kw in w)
            score += 2 * sum(1 for t in tags if kw in t)
            score += 1 * sum(1 for w in desc_words if kw in w)

        if score > 0:
            scored.append((score, listing))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [listing for _, listing in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    try:
        client = _get_groq_client()
        item_summary = (
            f"Item: {new_item['title']}\n"
            f"Category: {new_item['category']}\n"
            f"Colors: {', '.join(new_item['colors'])}\n"
            f"Style tags: {', '.join(new_item['style_tags'])}\n"
            f"Condition: {new_item['condition']}\n"
            f"Price: ${new_item['price']:.2f} on {new_item['platform']}"
        )

        wardrobe_items = wardrobe.get("items", [])

        if not wardrobe_items:
            prompt = (
                f"A user is considering buying this thrifted item:\n{item_summary}\n\n"
                "They haven't added any wardrobe items yet. Give them 1–2 specific outfit ideas "
                "for this piece based on its style, colors, and category. Suggest what types of "
                "bottoms, shoes, or outerwear would pair well. Be specific about silhouettes and "
                "styling details. Keep it casual and direct — like advice from a friend who knows fashion."
            )
        else:
            wardrobe_text = "\n".join(
                f"- {item['name']} ({item['category']}, {', '.join(item['colors'])})"
                + (f" — {item['notes']}" if item.get("notes") else "")
                for item in wardrobe_items
            )
            prompt = (
                f"A user is considering buying this thrifted item:\n{item_summary}\n\n"
                f"Their current wardrobe includes:\n{wardrobe_text}\n\n"
                "Suggest 1–2 complete outfit combinations using the new item and named pieces "
                "from their wardrobe. Reference specific wardrobe items by name. Include shoes "
                "and any relevant outerwear or accessories from the wardrobe. Be specific about "
                "styling details (tuck, layer, roll sleeves, etc.). Keep the tone casual and "
                "direct — like advice from a friend who knows fashion."
            )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=400,
        )
        result = response.choices[0].message.content.strip()
        return result if result else "This piece has great potential — try pairing it with high-waisted bottoms and clean sneakers."
    except Exception:
        return "I couldn't generate outfit suggestions right now. Try pairing this item with similar-colored basics in your wardrobe."


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return (
            "Couldn't generate a fit card — outfit suggestion was missing. "
            "Make sure suggest_outfit ran successfully first."
        )

    try:
        client = _get_groq_client()
        prompt = (
            f"Write a 2–4 sentence Instagram/TikTok caption for this thrifted outfit.\n\n"
            f"The thrifted item: {new_item['title']} — ${new_item['price']:.2f} from {new_item['platform']}\n"
            f"The full outfit: {outfit}\n\n"
            "Requirements:\n"
            "- Sound like a real person posting their OOTD, not a product description\n"
            "- Mention the item name, price, and platform naturally — once each\n"
            "- Capture the specific vibe of the outfit (don't just say 'cute' or 'love it')\n"
            "- Keep it casual and specific — like something your stylish friend would actually post\n"
            "- 2–4 sentences max, no hashtags needed"
        )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=150,
        )
        result = response.choices[0].message.content.strip()
        return result if result else "Fit card unavailable right now, but your look sounds amazing."
    except Exception:
        return "Fit card unavailable right now, but your look sounds amazing."
