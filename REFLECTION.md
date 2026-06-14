# FitFindr — Reflection

## Milestone 1: Planning

**What did you spec out in planning.md, and why did you make those choices?**

I specced three tools: `search_listings` (keyword scoring), `suggest_outfit` (LLM outfit combos), and `create_fit_card` (LLM caption). The most important design decision was the scoring system for search — title gets 3 points, style tags get 2, description gets 1. That weighting means an exact title match always beats a keyword that only appears buried in a description, which gives better results without needing an embedding model.

The other significant decision was query parsing: instead of regex, I use the Groq LLM at temperature=0 to extract description, size, and max_price from natural language. This handles edge cases like "under $30" vs "max $30" vs "budget 30 dollars" without me having to anticipate every phrasing. The temp=0 makes it deterministic for the same input.

The planning loop has a hard early exit: if search returns an empty list, the agent stops immediately and never passes empty data to `suggest_outfit` or `create_fit_card`. This prevents a whole class of downstream errors without needing defensive checks in every downstream tool.

---

## Milestone 2: Data Exploration

**What did you find in the listings dataset?**

40 listings across 6 categories (tops, bottoms, outerwear, shoes, accessories, dresses) and multiple style aesthetics (vintage, y2k, grunge, cottagecore, streetwear, minimalist). Prices range from about $8 to $85. Sizes are non-standardized — some use "M", some "S/M", shoes use "US 8", pants use "W30 L30". That's why I implemented size filtering as a case-insensitive substring match (`"m" in listing["size"].lower()`) rather than exact match — it handles "M" matching "S/M" naturally.

---

## Milestone 3: Tool Implementation

**What was the hardest tool to implement?**

`suggest_outfit` had the most moving parts. The two-branch logic (empty wardrobe vs. populated wardrobe) required writing two distinct prompts, and formatting the wardrobe items into the prompt text in a readable way took some iteration. I format each item as `"- {name} ({category}, {colors}) — {notes}"` so the LLM can reference pieces by name naturally in its suggestions.

The `search_listings` scoring loop looked simple but had a subtle decision: I drop zero-score items entirely rather than returning everything sorted. This matters — if a user searches "vintage tee" and there are listings that don't contain either word anywhere, they shouldn't appear at all, even at the bottom of the list.

---

## Milestone 4: Planning Loop

**How does your agent decide which tools to call?**

The loop is linear with one conditional branch. It always runs: parse → search. If search returns anything, it continues: select → outfit → fit card → return. If search returns nothing, it stops immediately with an error message.

There's no dynamic replanning or backtracking — this agent doesn't decide mid-run to call a different tool based on what the previous one returned. The branching is purely structural: empty list = stop, non-empty list = continue. This is the right level of complexity for a three-step pipeline where each step's output type is always the same.

**What was the most important state management decision?**

Using a session dict as the single source of truth. Every tool in the chain receives values from the session and writes results back to it. This means each tool only knows what it needs — `suggest_outfit` receives `selected_item` and `wardrobe`, not the raw search results. It can't accidentally use a different item than the one that was selected. The session is also what gets returned to `handle_query()` in app.py — one object carries everything, including the error state.

---

## Milestone 5: Failure Modes

**What three failure modes did you test, and what did the agent do?**

**1. No search results:**
Query: `"designer ballgown size XXS under $5"`
Behavior: search_listings returns `[]` → agent sets `session["error"]` to "No listings found for 'designer ballgown', size XXS under $5. Try a broader description, raise your price limit, or remove the size filter." and returns immediately. The outfit and fit card panels in the UI are blank. No downstream tools are called.

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
| M1 Planning | Generated the architecture diagram structure | Read through all spec fields and confirmed they match the actual implementation |
| M3 Tools | Generated `search_listings`, `suggest_outfit`, `create_fit_card` bodies from specs in planning.md | Ran 11 unit tests, confirmed price/size filtering, checked score ordering |
| M4 Loop | Generated `run_agent()` body from planning.md architecture diagram | Ran `python agent.py` with both happy-path and no-results queries, confirmed session state |
| M4 UI | Generated `handle_query()` body from the TODO docstring | Read through the output format, confirmed listing_text includes all required fields |
| M6 README | First draft of all sections | Confirmed commands actually work, checked section completeness |
