# FitFindr — Reflection

## Milestone 1: Planning

**What did you spec out in planning.md, and why did you make those choices?**

I specced three tools: `search_listings` (keyword scoring), `suggest_outfit` (LLM outfit combos), and `create_fit_card` (LLM caption). The most important design decision was the scoring system for search — title gets 3 points, style tags get 2, description gets 1. That weighting means an exact title match always beats a keyword that only appears buried in a description, which gives better results without needing an embedding model.

The other significant decision was query parsing: instead of regex, I use the Groq LLM at temperature=0 to extract description, size, and max_price from natural language. This handles edge cases like "under $30" vs "max $30" vs "budget 30 dollars" without me having to anticipate every phrasing. The temp=0 makes it deterministic for the same input.

The planning loop has a hard early exit: if search returns an empty list, the agent stops immediately and never passes empty data to `suggest_outfit` or `create_fit_card`. This prevents a whole class of downstream errors without needing defensive checks in every downstream tool.

---

## Milestone 2: Data Exploration

**What did you find in the listings dataset?**

The project moved from a static mock dataset to the live eBay Browse API, so data exploration meant understanding what real eBay secondhand listings actually look like. The biggest finding was inconsistency: sizes are listed in every format imaginable — "M", "S/M", "US 8", "W30 L30", or not listed at all. That's why size filtering is implemented as a post-fetch case-insensitive substring match rather than an exact match, so "M" matches "S/M" naturally.

Price data was reliable — eBay enforces it — but the `size` and `brand` fields frequently come back empty. Items without a size get normalized to `"Not listed"` so downstream tools always have a string to work with rather than a null. The other key finding: eBay's keyword matching is broad, so a vague query like "jacket" can return hundreds of unrelated results. That's what motivated adding an LLM keyword-generation step (`_generate_ebay_keywords`) that tightens the search terms before hitting the API.

---

## Milestone 3: Tool Implementation

**What was the hardest tool to implement?**

`search_ebay` had the most moving parts. It required OAuth2 client credentials authentication with a token cached at module scope so it doesn't re-authenticate on every search, an LLM call to generate tighter eBay keywords from the user's natural language description, the actual eBay Browse API request with price and category filters, and then normalizing every returned item into a consistent schema. Any of those four steps failing in the wrong order would break the whole tool silently.

`suggest_outfit` was the second-hardest. The two-branch logic — empty wardrobe vs. populated wardrobe — required writing two distinct LLM prompts, and formatting wardrobe items into the prompt in a readable way took iteration. Each item is formatted as `"- {name} ({category}, {colors}) — {notes}"` so the LLM can reference pieces by name naturally in its output rather than just describing a vibe.

---

## Milestone 4: Planning Loop

**How does your agent decide which tools to call?**

The loop is linear with two hard conditional exits. It always runs: validate → parse → search. If `validate_query` returns `valid: False`, the agent sets `session["error"]` and returns immediately — no eBay call is made. If `search_ebay` returns an empty list, the agent sets `session["error"]` and returns again. Only when search returns results does the pipeline continue into `suggest_outfit` and `create_fit_card`.

There's no dynamic replanning or backtracking — this agent doesn't decide mid-run to call a different tool based on what the previous one returned. The branching is purely structural: invalid query = stop, empty results = stop, results found = continue. This is the right level of complexity for a pipeline where each step's output type is always the same.

**What was the most important state management decision?**

Using a session dict as the single source of truth. Every tool in the chain receives values from the session and writes results back to it. This means each tool only knows what it needs — `suggest_outfit` receives `selected_item` and `wardrobe`, not the raw search results. It can't accidentally use a different item than the one that was selected. The session is also what gets returned to `handle_query()` in app.py — one object carries everything, including the error state.

---

## Milestone 5: Failure Modes

**What three failure modes did you test, and what did the agent do?**

**1. No search results:**
Query: `"vintage silk kimono size XXXL under $1"`
Behavior: `search_ebay` returns `[]` — eBay has no listings matching that size and price combination → agent sets `session["error"]` to an actionable message ("Try a broader description, raise your price limit, or remove the size filter.") and returns immediately. The outfit and fit card panels in the UI are blank. No downstream tools are called.

**2. Empty wardrobe:**
Query: `"vintage graphic tee under $30"` with "Empty wardrobe (new user)" selected
Behavior: `suggest_outfit` detects `wardrobe['items'] == []` and switches to a general styling prompt. The LLM returns generic but specific advice like "This boxy tee pairs well with high-waisted straight-leg jeans and chunky sneakers for a 90s streetwear look." No exception, no empty string.

**3. Empty outfit string into create_fit_card:**
Tested via unit test (`test_fit_card_empty_outfit_no_exception`):
```python
create_fit_card("", results[0])  # returns error string, no exception
```
Behavior: the guard clause fires immediately and returns "Couldn't generate a fit card — outfit suggestion was missing. Make sure suggest_outfit ran successfully first." No LLM call is made.

All 11 tests pass. All three failure modes are handled gracefully.

---

## Milestone 6: Final Demo

**What does the agent do well?**

The search results are surprisingly good for a simple keyword scorer. A query like "vintage graphic tee" correctly surfaces band tees and bootleg-style shirts above unrelated vintage items because the scoring weights title heavily. The outfit suggestions are specific and name-drop wardrobe pieces directly, which makes them actually useful rather than generic. The fit card reads like something a real person would post — casual, with natural price and platform mentions.

**What would you improve with more time?**

The query parsing occasionally strips meaningful style words (it extracted "vintage graphic tee" from "looking for a vintage graphic tee under $30" correctly, but more complex queries with multiple constraints can lose nuance). A better approach would be few-shot examples in the parsing prompt.

The fit card is the weakest output — at temperature=0.9 it's creative, but it sometimes over-indexes on the thrift angle and writes captions that feel promotional rather than personal. Training the prompt with actual examples of good OOTD posts would help.

**What did you learn about building multi-tool agents?**

The most important lesson: the planning loop is not the hard part — it's just a function with an if-statement. The hard part is state management and making sure each tool handles bad input gracefully so upstream errors don't cascade into crashes downstream. The empty-wardrobe and empty-outfit guards are simple checks, but without them the whole pipeline would break on a completely normal user action (being a new user with no wardrobe).

The second lesson: deterministic LLM calls (temperature=0) for structured extraction are reliable, but you still need to strip markdown code fences from the output before parsing. LLMs trained on code will often wrap JSON in triple-backtick blocks even when you explicitly ask for raw JSON.

---

## AI Tool Usage Log

| Milestone | What I used AI for | What I verified manually |
|-----------|-------------------|--------------------------|
| M1 Planning | Generated the architecture diagram and session dict schema | Read through all spec fields and confirmed they matched the planned function signatures |
| M3 Tools | Generated `search_ebay`, `suggest_outfit`, `create_fit_card`, and `validate_query` bodies from specs in planning.md | Ran 11 unit tests; caught and fixed a bug where zero-score items weren't filtered before sorting; confirmed size/price filtering behavior |
| M4 Loop | Generated `run_agent()` body from planning.md architecture diagram | Ran `python agent.py` with happy-path and no-results queries; caught missing early `return session` after error-set that caused crash on empty results |
| M4 UI | Generated `handle_query()` and Gradio layout from the TODO docstrings | Verified all 9 output values wired correctly; confirmed pill nav and "View more" pagination work end-to-end |
| M6 README + REFLECTION | First draft of all sections | Updated tool names from `search_listings` to `search_ebay`, corrected no-results test query, confirmed all commands still run |
