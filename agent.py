"""
agent.py — FitFindr v2

Planning loop:
    1. Validate query (reject off-topic, allow fashion adjectives)
    2. Parse natural language → description, size, max_price
    3. Search eBay for real secondhand listings
    4. Early exit if no results
    5. Suggest outfits (incorporating style_goal if given)
    6. Generate fit card
    7. Return session dict
"""

import json
import os
import re

from dotenv import load_dotenv
from groq import Groq

from tools import validate_query, search_ebay, suggest_outfit, create_fit_card

load_dotenv()


# ── Query parser ──────────────────────────────────────────────────────────────

def _parse_query(query: str, style_goal: str | None = None) -> dict:
    """
    Use LLM to extract description, size, and max_price from natural language.
    style_goal is mentioned in context so the LLM can disambiguate clothing intent.
    """
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        style_context = f"\nStyle goal: {style_goal}" if style_goal else ""
        prompt = (
            "Extract structured search parameters from this clothing query.\n"
            f'Query: "{query}"{style_context}\n\n'
            "Return ONLY a JSON object with these exact keys:\n"
            '  "description": the item type and style keywords (str)\n'
            '  "size": the size if mentioned, otherwise null\n'
            '  "min_price": the minimum price as a float if mentioned ("between $20 and $50" → 20.0), otherwise null\n'
            '  "max_price": the maximum price as a float if mentioned ("under $50", "between $20 and $50" → 50.0), otherwise null\n\n'
            "Return only the JSON object, no explanation."
        )
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=130,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        parsed = json.loads(raw)
        return {
            "description": parsed.get("description") or query,
            "size":        parsed.get("size"),
            "min_price":   parsed.get("min_price"),
            "max_price":   parsed.get("max_price"),
        }
    except Exception:
        return {"description": query, "size": None, "min_price": None, "max_price": None}


# ── Session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict, style_goal: str | None) -> dict:
    return {
        "query":              query,
        "style_goal":         style_goal,
        "parsed":             {},
        "search_results":     [],
        "selected_item":      None,
        "wardrobe":           wardrobe,
        "outfit_suggestion":  None,
        "fit_card":           None,
        "error":              None,   # fatal — stops the pipeline
        "warning":            None,   # non-fatal info shown to the user
    }


# ── Planning loop ─────────────────────────────────────────────────────────────

def run_agent(
    query: str,
    wardrobe: dict,
    style_goal: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
) -> dict:
    """
    Main entry point for a single FitFindr interaction.

    Args:
        query:      Natural language user request.
        wardrobe:   Wardrobe dict (get_example_wardrobe or get_empty_wardrobe).
        style_goal: Optional aesthetic goal, e.g. "dark academia", "y2k streetwear".

    Returns:
        Session dict. Check session["error"] first — if not None, the pipeline
        stopped early. session["warning"] is non-fatal (query was borderline valid).
    """
    session = _new_session(query, wardrobe, style_goal)

    # ── Step 1: Validate query ────────────────────────────────────────────────
    validation = validate_query(query)
    if not validation["valid"]:
        session["error"] = (
            f"FitFindr searches secondhand clothing — your query doesn't look fashion-related. "
            f"{validation.get('warning', '')} "
            "Try searching for a clothing item, style aesthetic, or occasion."
        )
        return session

    # ── Step 2: Parse query ───────────────────────────────────────────────────
    session["parsed"] = _parse_query(query, style_goal)

    # ── Step 3: Search eBay ───────────────────────────────────────────────────
    # UI price inputs take precedence; fall back to what the LLM parsed from text
    effective_min = min_price if min_price is not None else session["parsed"].get("min_price")
    effective_max = max_price if max_price is not None else session["parsed"].get("max_price")
    try:
        session["search_results"] = search_ebay(
            description=session["parsed"]["description"],
            size=session["parsed"]["size"],
            min_price=effective_min,
            max_price=effective_max,
            style_goal=style_goal,
        )
    except RuntimeError as e:
        session["error"] = str(e)
        return session

    if not session["search_results"]:
        desc       = session["parsed"]["description"]
        size_hint  = f", size {session['parsed']['size']}" if session["parsed"]["size"] else ""
        if effective_min is not None and effective_max is not None:
            price_hint = f" between ${effective_min:.0f}–${effective_max:.0f}"
        elif effective_max is not None:
            price_hint = f" under ${effective_max:.0f}"
        elif effective_min is not None:
            price_hint = f" above ${effective_min:.0f}"
        else:
            price_hint = ""
        session["error"] = (
            f"No secondhand listings found for '{desc}'{size_hint}{price_hint}. "
            "Try different keywords, raise the price limit, or remove the size filter."
        )
        return session

    # ── Step 4: Select top result ─────────────────────────────────────────────
    session["selected_item"] = session["search_results"][0]

    # ── Step 5: Suggest outfit ────────────────────────────────────────────────
    session["outfit_suggestion"] = suggest_outfit(
        new_item=session["selected_item"],
        wardrobe=session["wardrobe"],
        style_goal=style_goal,
    )

    # ── Step 6: Generate fit card ─────────────────────────────────────────────
    session["fit_card"] = create_fit_card(
        outfit=session["outfit_suggestion"],
        new_item=session["selected_item"],
    )

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== Happy path: vintage tee ===\n")
    session = run_agent(
        query="vintage graphic tee under $40",
        wardrobe=get_example_wardrobe(),
        style_goal="90s streetwear",
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        item = session["selected_item"]
        print(f"Found: {item['title']} — ${item['price']:.2f}")
        print(f"Image: {item.get('image_url', 'n/a')}")
        print(f"Link:  {item.get('item_url', 'n/a')}")
        print(f"\nOutfit:\n{session['outfit_suggestion']}")
        print(f"\nFit card:\n{session['fit_card']}")

    print("\n\n=== Off-topic query rejection ===\n")
    session2 = run_agent(query="how do I make pasta carbonara", wardrobe=get_example_wardrobe())
    print(f"Error: {session2['error']}")
