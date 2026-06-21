# FitFindr

A multi-tool AI agent that helps users find secondhand clothing and figure out how to style it. Describe what you want in plain language — FitFindr searches live eBay listings, picks the best match, suggests a complete outfit based on your wardrobe, and writes a shareable social-media caption for the look.

**GitHub repository:** https://github.com/fortdominz/ai201-project2-fitfindr-starter

---

## What It Does

1. **Validates the query** — rejects off-topic input (food, tech, etc.) before any search happens; allows all fashion-adjacent language including style adjectives
2. **Understands natural language** — uses an LLM to extract a structured description, optional size, and optional price range from whatever the user types
3. **Searches live eBay listings** — calls the eBay Browse API with LLM-generated keywords, normalizes results into a consistent schema, and returns the best matches
4. **Suggests an outfit** — asks an LLM to build 1–2 complete outfit combinations using named pieces from the user's wardrobe (or gives general styling advice for new users)
5. **Generates a fit card** — writes a casual, specific 2–4 sentence Instagram/TikTok caption for the look, mentioning the item name, price, and platform naturally

---

## Tools

### `validate_query(user_query: str) -> dict`

**Purpose:** Guards the pipeline against off-topic input before any eBay search or LLM calls happen.

**Parameters:**
- `user_query` (`str`) — the raw text the user typed into the search box

**Returns:** `{"valid": bool, "warning": str | None}` — `valid: False` stops the pipeline immediately; `warning` carries a non-fatal message for borderline queries. Fails open: if the LLM call itself errors, `valid` is set to `True` so a network hiccup never blocks all searches.

---

### `search_ebay(description: str, size: str | None = None, min_price: float | None = None, max_price: float | None = None, style_goal: str | None = None) -> list[dict]`

**Purpose:** Searches live eBay secondhand listings and returns normalized results matching the user's item description, optional size, and optional price range.

**Parameters:**
- `description` (`str`) — natural-language item description extracted from the query (e.g., `"vintage graphic tee"`)
- `size` (`str | None`) — size string to filter results post-fetch, case-insensitive substring match (e.g., `"M"` matches `"S/M"`); `None` skips size filtering
- `min_price` (`float | None`) — minimum price inclusive; `None` means no floor
- `max_price` (`float | None`) — maximum price inclusive; `None` means no ceiling
- `style_goal` (`str | None`) — optional aesthetic goal (e.g., `"grunge"`) passed to the keyword generator to enrich the eBay search terms

**Returns:** A `list[dict]` of up to 5 normalized listing dicts, each with keys: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`, `image_url`, `item_url`. Returns `[]` if nothing matches — never raises on empty results.

---

### `suggest_outfit(new_item: dict, wardrobe: dict, style_goal: str | None = None) -> str`

**Purpose:** Calls the Groq LLM to generate 1–2 complete outfit combinations for the found item. Uses the user's real wardrobe items by name when available; switches to general styling advice for new users with an empty wardrobe.

**Parameters:**
- `new_item` (`dict`) — a normalized listing dict from `search_ebay()` (title, category, colors, size, condition, price, platform)
- `wardrobe` (`dict`) — a wardrobe dict with an `"items"` key containing a list of wardrobe item dicts; the list may be empty
- `style_goal` (`str | None`) — optional aesthetic goal passed to the LLM prompt to shape suggestions

**Returns:** A non-empty `str` with outfit suggestions, structured as double-newline-separated paragraphs (one per outfit option). Never returns an empty string — on LLM error, returns a safe fallback string.

---

### `create_fit_card(outfit: str, new_item: dict) -> str`

**Purpose:** Generates a short, shareable OOTD caption styled for Instagram or TikTok. Runs at temperature 0.9 so output varies across calls.

**Parameters:**
- `outfit` (`str`) — the outfit suggestion string returned by `suggest_outfit()`; guarded against empty/whitespace input before the LLM is called
- `new_item` (`dict`) — the normalized listing dict; used to mention the item name, price, and platform naturally in the caption

**Returns:** A `str` containing a 2–4 sentence caption. If `outfit` is empty or whitespace-only, returns a descriptive error string immediately without making an LLM call. On LLM error, returns a safe fallback string.

---

## Architecture & Planning Loop

```
User query (plain language)
        │
        ▼
run_agent() planning loop
    │
    ├─ 1. validate_query()  → LLM: is this fashion-related?
    │       └─ invalid? → set session["error"], RETURN immediately
    │
    ├─ 2. _parse_query()    → LLM (temp=0): extract description / size / max_price
    │
    ├─ 3. search_ebay()     → eBay Browse API → normalized listing dicts
    │       └─ empty? → set session["error"], RETURN immediately
    │
    ├─ 4. suggest_outfit()  → LLM outfit combos (wardrobe-aware or general)
    │
    └─ 5. create_fit_card() → LLM Instagram caption (temp=0.9)
        │
        ▼
    session dict → handle_query() in app.py → three Gradio output panels
```

**How the conditional logic works:** The loop has two hard early exits. After step 1, if `validate_query` returns `valid: False`, the agent sets `session["error"]` and returns the session immediately — no eBay call is made. After step 3, if `search_ebay` returns an empty list, the agent again sets `session["error"]` and returns — `suggest_outfit` and `create_fit_card` are never called. Steps 4 and 5 only ever run when step 3 returned at least one result. This conditional structure prevents any tool from receiving empty or invalid input from a failed upstream step.

---

## State Management

All state lives in a single session dict initialized at the start of `run_agent()`. Each tool reads from it and writes its result back to it — no tool re-fetches or recalculates values a previous step already produced.

| Key | Type | Set when | Read by |
|-----|------|----------|---------|
| `query` | `str` | On init | Logging, display |
| `style_goal` | `str \| None` | On init | `search_ebay`, `suggest_outfit` |
| `parsed` | `dict` | After `_parse_query()` | `search_ebay` (description, size, price params) |
| `search_results` | `list[dict]` | After `search_ebay()` | Selecting `selected_item`; early-exit check |
| `selected_item` | `dict` | After search (if results > 0) | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | `dict` | On init (passed in) | `suggest_outfit` |
| `outfit_suggestion` | `str` | After `suggest_outfit()` | `create_fit_card`, UI outfit panel |
| `fit_card` | `str` | After `create_fit_card()` | UI fit card panel |
| `error` | `str \| None` | On early exit | `handle_query()` — shown in listing panel; stops UI from rendering outfit/fitcard |
| `warning` | `str \| None` | By `validate_query` on borderline queries | `handle_query()` — shown above results, non-fatal |

The session is the only object returned to `handle_query()` — one dict carries all outputs, the error state, and the warning state together.

---

## Failure Modes Handled

| Tool | Failure | Agent response |
|------|---------|----------------|
| `validate_query` | Query is off-topic (e.g., "best pizza recipe") | Sets `session["error"]`, returns immediately. No eBay call or LLM calls are made. |
| `search_ebay` | No listings match (e.g., "designer ballgown size XXS under $5") | Sets `session["error"]` = "No listings found. Try a broader description, raise your price limit, or remove the size filter." Returns immediately. Outfit and fit card panels stay empty. |
| `suggest_outfit` | Wardrobe is empty (`wardrobe["items"] == []`) | Switches to a general styling prompt instead of wardrobe-specific combos. Returns advice like "This pairs well with high-waisted straight-leg jeans and chunky sneakers." Never returns empty string. |
| `create_fit_card` | `outfit` is empty or whitespace-only | Guard clause fires before the LLM is called and returns "Couldn't generate a fit card — outfit suggestion was missing." Confirmed via unit test `test_fit_card_empty_outfit_no_exception`. |

---

## Spec Reflection

**One way the spec helped:** Writing the session dict schema in planning.md before touching any code forced every tool's inputs and outputs to be decided up front. When it came time to implement `suggest_outfit`, the contract was already clear — it receives `selected_item` (not the full search results) and `wardrobe` (not a raw file path). That prevented a whole class of coupling bugs where tools reach into each other's internal state.

**One way implementation diverged from the spec:** The planning spec described `search_listings` as a local keyword scorer over 40 mock listings using a 3/2/1 title/tags/description weighting system. The actual implementation replaced this entirely with `search_ebay`, which calls the live eBay Browse API using LLM-generated keywords. The divergence happened because a mock dataset produces results that are too predictable to be useful in a demo — the same query always returns the same items. Using the real eBay API means every search returns current, real secondhand listings, which makes the outfit and fit card outputs genuinely useful rather than canned. The session dict interface (`search_results` as `list[dict]`) stayed the same, so no downstream tool needed to change.

---

## AI Tool Usage

**Instance 1 — Tool implementations (Milestone 3):**
I gave Claude the full spec block for each tool from planning.md — exact parameter names, types, scoring weights, return shapes, and failure modes — and asked it to implement the function bodies. The generated code was structurally correct but the `search_listings` implementation dropped zero-score items in the wrong place (after sorting, not before), which meant low-relevance results with score 0 could still appear at the bottom of the list. I caught this by running the test `test_search_returns_empty_on_no_match` and manually tracing the scoring loop. I revised the filter to `if score > 0` before the sort, so zero-score items are excluded entirely regardless of return order.

**Instance 2 — Planning loop (Milestone 4):**
I gave Claude the complete Architecture diagram from planning.md and asked it to implement `run_agent()` following the session-dict pattern. The generated code worked for the happy path but called `suggest_outfit` unconditionally — it stored the empty-list case in `session["error"]` but forgot the `return session` early exit, so the pipeline continued into `suggest_outfit` with `selected_item` unset and crashed. I identified the missing return statement by running `python agent.py` with the "designer ballgown" no-results test case pre-wired in `__main__` and reading the traceback. I added the early `return session` after the error-set line and re-ran both test cases to confirm.

---

## Setup

```bash
cd ai201-project2-fitfindr-starter
pip install -r requirements.txt
```

Create a `.env` file with your API keys:

```
GROQ_API_KEY=your_key_here
EBAY_CLIENT_ID=your_key_here
EBAY_CLIENT_SECRET=your_key_here
```

Get a free Groq key at console.groq.com. eBay credentials are from developer.ebay.com.

---

## Running the App

```bash
python app.py
```

Open `http://localhost:7860` in your browser.

**Example queries to try:**
- `vintage graphic tee under $30`
- `90s track jacket in size M`
- `flowy midi skirt under $40`
- `black combat boots size 8`
- `designer ballgown size XXS under $5` ← triggers the no-results branch
- `best pizza recipe` ← triggers query validation rejection

**Wardrobe toggle:** Switch between "Demo wardrobe" (10 real items) and "Empty wardrobe (new user)" to see how outfit suggestions adapt.

---

## Testing

```bash
pytest tests/ -v
```

11 tests covering all tools: search scoring, price/size filtering, empty wardrobe handling, and the `create_fit_card` empty-outfit guard. eBay tests skip automatically if credentials are missing from `.env`.

---

## Running the Agent Directly

```bash
python agent.py
```

Pre-wired happy path and no-results test cases run automatically.

---

## Tech Stack

- **Python 3.11**
- **Groq** (llama-3.3-70b-versatile) — query validation, query parsing, outfit suggestions, fit card generation
- **eBay Browse API** — live secondhand listing search
- **Gradio** — web UI
- **python-dotenv** — API key management
- **pytest** — tool isolation tests
