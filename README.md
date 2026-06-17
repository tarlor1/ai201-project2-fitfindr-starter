# FitFindr

FitFindr is an AI-powered secondhand shopping assistant. Give it a natural language query describing what you're looking for, and it finds a matching thrifted listing, suggests outfit combinations using your existing wardrobe, and generates a shareable OOTD caption.

---

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (free key at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

Run the Gradio UI:

```bash
python app.py
```

Run tests:

```bash
pytest tests/
```

---

## Project Structure

```
fitfindr/
├── agent.py              # Planning loop (run_agent)
├── tools.py              # Three tools: search_listings, suggest_outfit, create_fit_card
├── app.py                # Gradio UI
├── planning.md           # Design spec
├── tests/
│   └── test_tools.py     # Pytest suite for all three tools
├── data/
│   ├── listings.json     # 40 mock secondhand listings
│   └── wardrobe_schema.json
└── utils/
    └── data_loader.py    # load_listings(), get_example_wardrobe(), get_empty_wardrobe()
```

---

## Tool Inventory

### `search_listings`

**Purpose:** Searches the mock listings dataset for items matching a natural language description, with optional size and price filters. Returns results sorted by keyword relevance so the best match is always first.

**Inputs:**

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `description` | `str` | Keywords describing the item (e.g. `"vintage graphic tee"`) |
| `size` | `str \| None` | Clothing size to filter by. Case-insensitive substring match — `"M"` matches `"S/M"`. Pass `None` to skip. |
| `max_price` | `float \| None` | Maximum price inclusive. Pass `None` to skip. |

**Output:** `list[dict]` — matching listing dicts sorted best-first. Each dict has `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns `[]` (empty list) if nothing matches — never raises.

---

### `suggest_outfit`

**Purpose:** Calls the LLM to suggest 1–2 complete outfits pairing the thrifted item with pieces from the user's existing wardrobe. If the wardrobe is empty, falls back to general styling advice instead of crashing.

**Inputs:**

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `new_item` | `dict` | A listing dict — the item the user is considering buying |
| `wardrobe` | `dict` | Wardrobe dict with an `items` key containing a list of wardrobe item dicts. May be empty. |

**Output:** `str` — a non-empty outfit suggestion string from the LLM. Uses `llama-3.3-70b-versatile` at temperature 0.7.

---

### `create_fit_card`

**Purpose:** Generates a 2–4 sentence Instagram/TikTok-style OOTD caption for the thrifted find. Uses a higher LLM temperature (1.1) so output varies across calls.

**Inputs:**

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `outfit` | `str` | The outfit suggestion string from `suggest_outfit` |
| `new_item` | `dict` | The listing dict for the thrifted item |

**Output:** `str` — a casual OOTD caption mentioning item name, price, and platform naturally. If `outfit` is empty or whitespace-only, returns a descriptive error string instead of raising.

---

## Planning Loop

The agent uses a **hardcoded planning loop** (Architecture B): Python drives the sequence of tool calls, not the LLM. The LLM is only called inside individual steps — it does not decide what happens next.

`run_agent(query, wardrobe)` executes these steps in order:

1. **Parse the query** — sends the raw query to the LLM with a structured extraction prompt asking for `description`, `size`, and `max_price` as JSON. Parses the response and stores the result in `session["parsed"]`. Returns early with an error if the JSON is malformed.

2. **Search listings** — calls `search_listings()` with the parsed parameters. Stores results in `session["search_results"]`. If the list is empty, sets `session["error"]` and returns immediately — `suggest_outfit` and `create_fit_card` are never called.

3. **Pick top result** — sets `session["selected_item"] = session["search_results"][0]`. The list is already sorted by relevance score, so index 0 is the best match.

4. **Suggest outfit** — calls `suggest_outfit(selected_item, wardrobe)`, stores the result in `session["outfit_suggestion"]`. Guards against an empty return string.

5. **Create fit card** — calls `create_fit_card(outfit_suggestion, selected_item)`, stores the result in `session["fit_card"]`.

6. **Return session** — callers check `session["error"]` first. `None` means success; a string means early termination.

---

## State Management

All state lives in a single `session` dict created by `_new_session()` at the start of each `run_agent` call. No global variables; no state that persists between calls.

| Key | Written by | Read by | Contains |
| --- | ---------- | ------- | -------- |
| `session["query"]` | `_new_session()` | Step 1 | Original user query string |
| `session["parsed"]` | Step 1 (LLM parser) | Step 2 | `{description, size, max_price}` |
| `session["search_results"]` | Step 2 | Step 2 branch | Full sorted list from `search_listings` |
| `session["selected_item"]` | Step 2 (after branch) | Steps 3, 4 | Top listing dict, passed into both LLM tools |
| `session["wardrobe"]` | `_new_session()` | Step 3 | User's wardrobe dict, never modified |
| `session["outfit_suggestion"]` | Step 3 | Step 4 | Outfit string from `suggest_outfit` |
| `session["fit_card"]` | Step 4 | UI / caller | Caption string from `create_fit_card` |
| `session["error"]` | Any early exit | UI / caller | `None` on success; error message string otherwise |

Each step writes only its own key. If `session["error"]` is set, all downstream keys stay `None`.

---

## Error Handling

### `search_listings` — no results

**Failure mode:** Query, size, or price constraints are too narrow and no listing scores above zero.

**Agent response:** Sets `session["error"]` to a message that names what was searched and suggests fixes. Returns session immediately — `suggest_outfit` and `create_fit_card` are never called.

**Concrete test:**
```
$ python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
[]

$ python -c "
from agent import run_agent
from utils.data_loader import get_example_wardrobe
s = run_agent('designer ballgown size XXS under 5', get_example_wardrobe())
print(s['error'])
print(s['fit_card'])
"
No listings found for 'designer ballgown'. Try broader keywords, a higher price limit, or remove the size filter.
None
```

### `suggest_outfit` — empty wardrobe

**Failure mode:** The user has no wardrobe items on file.

**Agent response:** The tool detects `wardrobe["items"] == []` and switches to a general styling prompt ("what types of pieces pair well with this item, what vibe it suits"). Returns a non-empty string — the agent does not set an error and continues normally to `create_fit_card`.

**Concrete test:**
```
$ python -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe
item = search_listings('vintage graphic tee', max_price=50)[0]
print(suggest_outfit(item, get_empty_wardrobe()))
"
# Output: multi-sentence general styling advice — no exception raised
```

### `create_fit_card` — missing outfit string

**Failure mode:** `outfit` argument is empty or whitespace-only.

**Agent response:** The tool guards this at its top and returns a descriptive error string. It never raises an exception. `session["error"]` is left `None` because the tool communicated the problem through its return value.

**Concrete test:**
```
$ python -c "
from tools import search_listings, create_fit_card
item = search_listings('vintage graphic tee', max_price=50)[0]
print(create_fit_card('', item))
"
Error: outfit data is missing — cannot generate a fit card.
```

---

## Spec Reflection

### What matched

The implemented planning loop matches the planning.md spec exactly: LLM-based query parsing, `search_listings` as a pure Python filter-and-score step (no LLM), early return on empty results, session dict as the sole state carrier, and `create_fit_card` returning an error string rather than raising.

### What changed

**Query parsing method.** The original planning.md draft described regex patterns to extract `size` and `max_price` from the query string (e.g. matching `under \$?(\d+)`). During review, this was replaced with an LLM extraction call that returns structured JSON. The LLM approach handles natural phrasings like "no more than thirty bucks" that regex would miss, at the cost of one extra API round-trip per query.

**Walkthrough example vs. actual output.** The "Complete Interaction" section was drafted with a hypothetical "Faded Band Tee" as the top result. When the real agent ran, it returned the Y2K Baby Tee instead — also a vintage graphic tee under $30 in size S/M. The walkthrough was illustrative, not a contract, so no code changed; the planning.md step descriptions were accurate even though the specific listing name was not.

---

## AI Usage

### Instance 1 — Switching from regex to LLM query parsing

**What I gave the AI:** The original planning.md Planning Loop section, which described regex patterns for extracting `size` and `max_price` from the raw query string (e.g. `under \$?(\d+)`, `\b(XS|S|M|L|XL)\b`).

**What the AI produced:** An explanation of why regex is brittle for natural language (it misses "no more than thirty bucks", "keep it cheap", size written as "medium") and proposed an LLM-based alternative: send the raw query in a structured extraction prompt and parse the JSON response.

**What I changed:** Accepted the LLM approach. Updated the planning.md Planning Loop Step 1 to describe the JSON extraction prompt format. Added a `_parse_query()` helper to `agent.py` that strips markdown code fences from the response before parsing, since the LLM sometimes wraps its JSON in triple backticks.

### Instance 2 — Implementing the three tools in tools.py

**What I gave the AI:** The Tool 1, 2, and 3 spec blocks from planning.md (inputs with types, return values, failure modes), the `tools.py` stub file with its docstrings, and `data_loader.py` showing the listing dict shape.

**What the AI produced:** Complete implementations of all three functions. `search_listings` used `re.findall(r"\w+", ...)` to tokenize both the query and listing text for keyword scoring. `suggest_outfit` branched on `wardrobe["items"]` being empty. `create_fit_card` guarded on `outfit.strip() == ""`.

**What I changed:** Reviewed the scoring logic in `search_listings` — confirmed that single-character words were filtered out (`len(w) > 1`) to avoid common letters like "a" inflating scores. Verified `suggest_outfit` included wardrobe item `notes` in the prompt (e.g. "High-waisted, sits above the hip") so the LLM had richer context. Increased `create_fit_card` temperature from the default to 1.1 after observing that repeated calls on the same input produced nearly identical captions at lower temperatures.
