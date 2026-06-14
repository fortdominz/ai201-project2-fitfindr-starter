# FitFindr

A multi-tool AI agent that helps users find secondhand clothing and figure out how to style it. Describe what you want in plain language — FitFindr searches a mock thrift/resale dataset, picks the best match, suggests a complete outfit based on your wardrobe, and writes a shareable social-media caption for the look.

## What It Does

1. **Understands natural language** — uses an LLM to extract description, size, and max price from whatever the user types (e.g., "vintage graphic tee under $30, size M")
2. **Searches listings** — scores all 40 mock listings by keyword relevance across title, style tags, and description (weights: 3/2/1), filters by size and price, returns the best match
3. **Suggests an outfit** — asks an LLM to build 1–2 complete outfit combinations using named pieces from the user's wardrobe (or gives general styling advice if no wardrobe exists)
4. **Generates a fit card** — writes a casual, specific 2–4 sentence Instagram/TikTok caption for the look, mentioning the item name, price, and platform naturally

## Tools

| Tool | Description |
|------|-------------|
| `search_listings(description, size, max_price)` | Keyword-scored search over 40 mock secondhand listings. Returns ranked list; empty list on no match. |
| `suggest_outfit(new_item, wardrobe)` | LLM-powered outfit combinations using the user's wardrobe. Gracefully handles empty wardrobes. |
| `create_fit_card(outfit, new_item)` | LLM-generated OOTD caption (temperature=0.9 for variety). Guards against empty outfit input. |

## Architecture

```
User query (plain language)
        │
        ▼
run_agent() planning loop
    │
    ├─ 1. _parse_query()   → Groq LLM extracts description/size/max_price
    ├─ 2. search_listings() → keyword-scored, filtered results
    │       └─ empty? → set error, RETURN early
    ├─ 3. suggest_outfit()  → LLM outfit combos (wardrobe-aware or general)
    └─ 4. create_fit_card() → LLM Instagram caption (temp=0.9)
        │
        ▼
    session dict → handle_query() → three Gradio output panels
```

The session dict is the single source of truth — every tool reads from it and writes back to it. No tool re-fetches data already retrieved by a previous step.

## Failure Modes Handled

| Failure | Behavior |
|---------|----------|
| No listings match the query | Returns early with a helpful message ("Try a broader description, raise your price limit..."). Outfit and fit card panels stay empty. |
| Wardrobe is empty | `suggest_outfit` switches to a general styling prompt instead of a wardrobe-specific one. Never returns an empty string. |
| Empty outfit string reaches `create_fit_card` | Returns a descriptive error string immediately without calling the LLM. |

## Setup

```bash
# Clone and enter the project
cd ai201-project2-fitfindr-starter

# Install dependencies
pip install -r requirements.txt

# Add your Groq API key (get one free at console.groq.com)
echo "GROQ_API_KEY=your_key_here" > .env
```

## Running the App

```bash
python app.py
```

Open the URL shown in your terminal (usually `http://localhost:7860`).

**Example queries to try:**
- `vintage graphic tee under $30`
- `90s track jacket in size M`
- `flowy midi skirt under $40`
- `black combat boots size 8`
- `designer ballgown size XXS under $5` ← triggers the no-results branch

**Wardrobe toggle:** Switch between "Example wardrobe" (10 real items) and "Empty wardrobe (new user)" to see how outfit suggestions adapt.

## Testing

```bash
pytest tests/ -v
```

11 tests covering all three tools: search scoring, price/size filtering, empty wardrobe handling, and the `create_fit_card` empty-outfit guard.

## Running the Agent Directly

```bash
python agent.py
```

Pre-wired happy path and no-results test cases run automatically.

## Tech Stack

- **Python 3.11**
- **Groq** (llama-3.3-70b-versatile) — query parsing, outfit suggestions, fit card generation
- **Gradio** — web UI
- **python-dotenv** — API key management
- **pytest** — tool isolation tests
