# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the app (serves at http://localhost:7860)
python app.py

# Run all tests
pytest tests/ -v

# Run a single test
pytest tests/test_tools.py::test_validate_fashion_query_passes -v

# Run the agent pipeline directly (pre-wired happy-path + rejection test)
python agent.py
```

**eBay tests skip automatically** if `EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET` are missing from `.env`. All other tests run against the live Groq API and take ~8 seconds.

## Required Environment Variables

```
GROQ_API_KEY=...          # console.groq.com — always required
EBAY_CLIENT_ID=...        # developer.ebay.com — required for live search
EBAY_CLIENT_SECRET=...    # developer.ebay.com — required for live search
```

## Architecture

```
User input (query + optional style_goal + wardrobe choice)
    │
    ▼
agent.run_agent(query, wardrobe, style_goal)
    │
    ├── tools.validate_query()          LLM — reject off-topic, allow fashion adjectives
    ├── _parse_query()                  LLM — extract description/size/max_price
    ├── tools.search_ebay()             eBay Browse API v1 → up to 5 normalized items
    │       └─ _generate_ebay_keywords()   LLM translates description+style_goal → tight keywords
    │       └─ _get_ebay_token()           OAuth2 client_credentials, cached 2hr in module scope
    ├── tools.suggest_outfit()          LLM — 1-2 outfit options, wardrobe-aware, style_goal-aware
    └── tools.create_fit_card()         LLM — OOTD caption (temp=0.9)
    │
    ▼
app.handle_query() → (listing_html, outfit_html, fitcard_md, warning_html)
    │
    ▼
Gradio UI — 4 outputs, 3 inputs (query, wardrobe_choice, style_goal)
```

### File Responsibilities

- **`tools.py`** — all 4 tools plus their private helpers (`_get_ebay_token`, `_normalize_ebay_item`, `_generate_ebay_keywords`, `_guess_category`). Each tool is independently testable.
- **`agent.py`** — `run_agent()` only. Orchestrates tools via a session dict. No tool logic lives here.
- **`app.py`** — Gradio UI, CSS, JS, `_format_listing_html()`, `_format_outfit_html()`. No agent or tool logic.
- **`utils/data_loader.py`** — loads `data/wardrobe_schema.json` for the demo/empty wardrobe. `data/listings.json` is v1 only and no longer used.

### Session Dict

`run_agent()` returns a session dict — the single source of truth passed through the pipeline:

```python
{
    "query", "style_goal",      # inputs
    "parsed",                   # {description, size, max_price}
    "search_results",           # list of normalized eBay item dicts
    "selected_item",            # search_results[0]
    "wardrobe",                 # from data_loader
    "outfit_suggestion",        # str from suggest_outfit
    "fit_card",                 # str from create_fit_card
    "error",                    # str → pipeline stopped early; None on success
    "warning",                  # str → non-fatal info shown to user; None if clean
}
```

### Normalized Listing Schema

`search_ebay()` returns items normalized to this shape (same schema expected by `suggest_outfit`, `create_fit_card`, and `_format_listing_html`):

```python
{
    "id", "title", "description", "category", "style_tags",
    "size",        # "Not listed" when eBay doesn't provide it
    "condition",   # eBay string: "Good", "Very Good", "Used", etc.
    "price",       # float
    "colors",      # list[str], may be empty
    "brand",       # str | None
    "platform",    # always "eBay" in v2
    "image_url",   # thumbnail from eBay CDN, may be ""
    "item_url",    # full eBay listing URL, may be ""
}
```

## Gradio-Specific Gotchas

- **`css=` and `theme=` go to `demo.launch()`**, not `gr.Blocks()`. Gradio 6.x raises a warning and ignores them if placed on `Blocks`.
- **`<script>` tags inside `gr.HTML()` are stripped** by Gradio. JavaScript must go in `demo.load(fn=None, js=...)` or `component.event(fn=None, js=...)`.
- **Combining `fn` + `js` on the same event is unreliable** in Gradio 6.x — the JS may not fire before the server round-trip. Use `fn=None, js=...` for pure client-side actions. The theme toggle uses this pattern.
- **Theme switching** uses `body.classList.toggle('ff-light')` (not `html[data-ff-theme]`). All light-mode CSS is prefixed `body.ff-light .selector`. The button label is driven by CSS `::after` content, not Python state.

## Outfit HTML Format

`_format_outfit_html()` in `app.py` parses the LLM's outfit text by `\n\n`. Structure it expects:
- Paragraph 1 → intro line (shown above accordions)
- Middle paragraphs → one accordion ("Option N") each, body split into numbered steps
- Last paragraph → closing line IF it starts with words like "both", "either", "enjoy", "feel free" etc.

The LLM prompts in `suggest_outfit()` explicitly ask for this `\n\n`-separated paragraph structure.

## Query Validation Behavior

`validate_query()` fails **open** — if the Groq call itself errors, the query is allowed through. This prevents an LLM failure from breaking every search. Off-topic queries get a `session["error"]` that stops the pipeline; borderline queries can set `session["warning"]` (non-fatal, shown above results).

Fashion-adjacent adjectives ("sexy", "edgy", "bold", "flirty") are explicitly allowed by the validator prompt and must never be rejected.
