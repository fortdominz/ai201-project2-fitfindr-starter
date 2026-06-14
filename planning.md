# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## A Complete Interaction (Step by Step)

FitFindr is a multi-tool agent that helps users find secondhand clothing and figure out how to wear it. A user describes what they want in plain language; the agent searches a mock listings dataset, picks the top result, asks an LLM to suggest a complete outfit based on the user's existing wardrobe, and then generates a shareable social-media caption for the look. If the search finds no matching items, the agent stops immediately and tells the user what to try differently — it never calls the outfit or fit-card tools on empty input.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:** The agent parses the query using the Groq LLM to extract three values:
- description = "vintage graphic tee"
- size = None (not specified)
- max_price = 30.0

**Step 2:** `search_listings("vintage graphic tee", size=None, max_price=30.0)` is called.
It filters all 40 listings by price (≤ $30), scores each survivor by keyword overlap with "vintage graphic tee" across title, style_tags, and description (weighted 3/2/1), drops zero-score items, and returns a sorted list. Example result: `[{lst_006: "Graphic Tee — 2003 Tour Bootleg Style", $24, depop}, {lst_033: "Vintage Band Tee — Faded Grey", $19, depop}, ...]`

**Step 3:** The agent checks: results is not empty → `selected_item = results[0]` (the Graphic Tee). State is stored in `session["selected_item"]`.

**Step 4:** `suggest_outfit(new_item=<graphic tee dict>, wardrobe=<example wardrobe>)` is called.
The LLM receives the item details (title, style_tags, colors, condition) and a formatted list of the user's 10 wardrobe items and suggests 1–2 complete outfit combinations using named pieces. Example: "Pair this boxy graphic tee with your baggy straight-leg jeans and chunky white sneakers for a classic 90s streetwear look. Tuck the front corner slightly and add your black crossbody bag to keep it clean."

**Step 5:** `create_fit_card(outfit=<suggestion string>, new_item=<graphic tee dict>)` is called.
The LLM generates a casual 2–4 sentence Instagram-style caption. Example: "thrifted this faded bootleg tee off depop for $24 and it was made for my wide-legs 🖤 grabbed my chunky sneakers and called it an outfit, full look in bio"

**Final output to user:** Three panels in the Gradio UI:
- 🛍️ Top listing: title, price, platform, size, condition, style tags
- 👗 Outfit idea: the LLM's outfit suggestion string
- ✨ Fit card: the Instagram-style caption

**Error path:** If search_listings returns [] → session["error"] = "No listings matched your search. Try a broader description, a higher price limit, or remove the size filter." The agent returns immediately. Outfit and fit card panels stay empty.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock secondhand listings dataset and returns items that match the user's keyword description, optional size, and optional price ceiling. Results are sorted by relevance (best match first) using a weighted keyword scoring system across title, style tags, and description fields.

**Input parameters:**
- `description` (str): Keywords describing what the user is looking for (e.g., "vintage graphic tee"). Used for scoring — every word in the description is checked against each listing's title, style_tags, and description.
- `size` (str | None): Size string to filter by (e.g., "M", "L", "US 8"). Case-insensitive substring match against the listing's size field. None means skip size filtering entirely.
- `max_price` (float | None): Maximum price, inclusive. None means no price ceiling.

**What it returns:**
A list of listing dicts, sorted by relevance score (highest first). Each dict has: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str | None), `platform` (str). Returns an empty list `[]` if nothing matches — never raises an exception.

**Scoring weights:**
- title word match: 3 points per word
- style_tag exact match: 2 points per tag
- description word match: 1 point per word
All comparisons are lowercase.

**What happens if it fails or returns nothing:**
Returns `[]`. The planning loop checks for this: if `search_results` is empty, the agent sets `session["error"]` to a specific, actionable message ("No listings found. Try a broader description, a higher price limit, or remove the size filter.") and returns the session immediately without calling the next two tools.

---

### Tool 2: suggest_outfit

**What it does:**
Given the thrifted item the user is considering and their existing wardrobe, calls the Groq LLM to suggest 1–2 complete outfit combinations using named pieces from the wardrobe. If the wardrobe is empty, returns general styling advice for the item's vibe and category rather than crashing or returning an empty string.

**Input parameters:**
- `new_item` (dict): A listing dict from search_listings — contains title, description, style_tags, colors, condition, price, platform, and category.
- `wardrobe` (dict): A wardrobe dict with an `items` key containing a list of wardrobe item dicts. Each wardrobe item has: id, name, category, colors (list), style_tags (list), notes (str | None). The list may be empty.

**What it returns:**
A non-empty string with outfit suggestions. If the wardrobe has items, the suggestions reference specific pieces by name (e.g., "your baggy straight-leg jeans"). If the wardrobe is empty, the suggestions are general but specific to the item's vibe (e.g., "this boxy tee pairs well with high-waisted straight-leg jeans and chunky sneakers for a 90s streetwear look"). Never returns an empty string.

**What happens if it fails or returns nothing:**
- Empty wardrobe: handled by calling the LLM with a modified prompt asking for general styling advice rather than wardrobe-specific combos. No exception.
- LLM error: catches exceptions and returns "I couldn't generate outfit suggestions right now. Try pairing this item with similar-colored basics in your wardrobe."

---

### Tool 3: create_fit_card

**What it does:**
Generates a short, shareable 2–4 sentence outfit caption — the kind someone would post on Instagram or TikTok — by calling the Groq LLM with the item details and the outfit suggestion. Runs at higher temperature (0.9) to produce varied output across multiple calls.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by suggest_outfit(). May not be empty or whitespace-only — guarded before calling the LLM.
- `new_item` (dict): The listing dict for the thrifted item. Used to naturally mention the item title, price, and platform in the caption.

**What it returns:**
A 2–4 sentence string styled like a real OOTD social media caption: casual, specific about the vibe, mentions the item name/price/platform naturally once each. Different every run for different inputs. Never returns an empty string.

**What happens if it fails or returns nothing:**
- Empty outfit string: returns `"Couldn't generate a fit card — outfit suggestion was missing. Make sure suggest_outfit ran successfully first."` without calling the LLM.
- LLM error: catches exceptions and returns `"Fit card unavailable right now, but your look sounds amazing."`.

---

### Additional Tools (if any)

None for required submission. Stretch feature (price comparison) would be added here if implemented.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop in `run_agent()` follows a strict linear conditional chain — each step only executes if the previous step succeeded:

```
Step 1: Initialize session via _new_session(query, wardrobe)

Step 2: Parse the user query using the Groq LLM.
        Ask it to extract description (str), size (str or null), and max_price
        (float or null) from the natural language query as JSON.
        Store in session["parsed"].

Step 3: Call search_listings(
            description=session["parsed"]["description"],
            size=session["parsed"]["size"],
            max_price=session["parsed"]["max_price"]
        )
        Store result in session["search_results"].

        Branch:
          IF session["search_results"] == []:
              session["error"] = "No listings found. Try a broader description,
                                  a higher price limit, or remove the size filter."
              RETURN session immediately  ← early exit, no more tool calls

          IF len(session["search_results"]) > 0:
              session["selected_item"] = session["search_results"][0]
              CONTINUE to Step 4

Step 4: Call suggest_outfit(
            new_item=session["selected_item"],
            wardrobe=session["wardrobe"]
        )
        Store result in session["outfit_suggestion"].

Step 5: Call create_fit_card(
            outfit=session["outfit_suggestion"],
            new_item=session["selected_item"]
        )
        Store result in session["fit_card"].

Step 6: RETURN session  ← normal exit
```

The agent does NOT call all three tools unconditionally. Only Step 3 (search) runs always. Steps 4 and 5 only run if Step 3 returned at least one result. The session dict is the single control surface — tools read from it and write to it; the loop checks it between steps.

---

## State Management

**How does information from one tool get passed to the next?**

All state lives in the session dict initialized by `_new_session()`. The fields and when they're set:

| Field | Type | When set | Used by |
|---|---|---|---|
| `query` | str | On init | Logging / display |
| `parsed` | dict | After query parsing | search_listings args |
| `search_results` | list[dict] | After search_listings | Selecting top item |
| `selected_item` | dict | After search (if results > 0) | suggest_outfit, create_fit_card |
| `wardrobe` | dict | On init (passed in) | suggest_outfit |
| `outfit_suggestion` | str | After suggest_outfit | create_fit_card |
| `fit_card` | str | After create_fit_card | UI output panel |
| `error` | str \| None | On early exit | UI — shown in listing panel |

No tool re-fetches or recalculates values set by a previous tool. `suggest_outfit` receives `session["selected_item"]` directly — it never re-runs the search. `create_fit_card` receives `session["outfit_suggestion"]` directly — it never re-runs the outfit suggestion. The session is the single source of truth.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No listings match the query (empty list returned) | Sets `session["error"]` = "No listings found for '[description]'. Try a broader description, raise your price limit, or remove the size filter." Returns session immediately. Outfit and fit card panels show empty. |
| suggest_outfit | Wardrobe is empty (`wardrobe['items'] == []`) | Calls the LLM with a general styling prompt instead of a wardrobe-specific one. Returns general advice like "This piece works well with high-waisted bottoms and sneakers for a streetwear look." Never returns empty string. |
| create_fit_card | Outfit string is empty or whitespace-only | Returns the string "Couldn't generate a fit card — outfit suggestion was missing." immediately without calling the LLM. If LLM errors for any other reason, catches the exception and returns "Fit card unavailable right now, but your look sounds amazing." |

---

## Architecture

```
User query (natural language)
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                        run_agent()                              │
│                      Planning Loop                              │
│                                                                 │
│  Step 1: _new_session(query, wardrobe) → session dict           │
│         │                                                       │
│  Step 2: Parse query → Groq LLM                                 │
│         │                                                       │
│         ▼ session["parsed"] = {description, size, max_price}    │
│                                                                 │
│  Step 3: search_listings(description, size, max_price)          │
│         │                                                       │
│         ├── results == [] ──────────────────────────────────┐   │
│         │                                                   │   │
│         │   session["error"] = "No listings found..."       │   │
│         │   RETURN session ◄─────────────────────────────── ┘   │
│         │                                                        │
│         └── results != [] ──────────────────────────────────┐   │
│                                                             │   │
│             session["search_results"] = [...]               │   │
│             session["selected_item"] = results[0]           │   │
│                                                             │   │
│  Step 4: suggest_outfit(selected_item, wardrobe) ◄──────────┘   │
│         │                                                        │
│         │   ┌─ wardrobe empty? → general styling advice          │
│         │   └─ wardrobe has items? → specific outfit combos      │
│         │                                                        │
│         ▼ session["outfit_suggestion"] = "..."                   │
│                                                                  │
│  Step 5: create_fit_card(outfit_suggestion, selected_item)       │
│         │                                                        │
│         │   ┌─ outfit empty? → return error string immediately   │
│         │   └─ outfit valid? → Groq LLM (temp=0.9) → caption     │
│         │                                                        │
│         ▼ session["fit_card"] = "..."                            │
│                                                                  │
│  Step 6: RETURN session                                          │
└──────────────────────────────────────────────────────────────────┘
         │
         ▼
    handle_query() in app.py
         │
         ├── session["error"] set?
         │     → listing_output = error message
         │     → outfit_output = ""
         │     → fitcard_output = ""
         │
         └── no error?
               → listing_output = formatted item card
               → outfit_output = session["outfit_suggestion"]
               → fitcard_output = session["fit_card"]
         │
         ▼
  Gradio UI: three output panels
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

For `search_listings`: I'll give Claude the Tool 1 spec block from this planning.md (what it does, exact input parameters, scoring weights, return value, failure mode) and ask it to implement the function using `load_listings()` from `utils/data_loader.py`. I'll verify the generated code: (1) filters by both max_price and size before scoring, (2) uses the 3/2/1 weighted scoring across title/style_tags/description, (3) drops zero-score items, (4) returns an empty list not an exception on no matches. Then I'll test with 3 queries: "vintage graphic tee" (expect results), "designer ballgown size XXS under $5" (expect []), "graphic tee under $25" (expect price filter working).

For `suggest_outfit`: I'll give Claude the Tool 2 spec (inputs, wardrobe format, two LLM prompt branches — empty vs. populated wardrobe, failure mode). I'll verify the generated code: (1) checks `wardrobe['items']` before building the prompt, (2) has a distinct prompt for the empty-wardrobe case, (3) catches LLM exceptions and returns the fallback string. I'll test with both `get_example_wardrobe()` and `get_empty_wardrobe()`.

For `create_fit_card`: I'll give Claude the Tool 3 spec (guard clause on empty outfit, caption style requirements, temperature=0.9). I'll verify: (1) empty outfit guard returns immediately without an LLM call, (2) the prompt instructs casual tone and specific item details, (3) temperature is 0.9 in the API call. I'll run it 3 times on the same input and confirm the outputs differ.

**Milestone 4 — Planning loop and state management:**

I'll give Claude the complete Architecture diagram above and the Planning Loop section. I'll ask it to implement `run_agent()` in agent.py following the 7 steps in the TODO exactly. I'll verify: (1) Step 3 branches on empty results and returns early, (2) Steps 4–5 only run if results exist, (3) every value is stored in `session` before being read by the next step, (4) the session is returned in all code paths. I'll test with `python agent.py` using both the happy-path and no-results cases pre-wired in the `__main__` block.
