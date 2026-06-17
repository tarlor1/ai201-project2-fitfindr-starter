# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
search_listings searches through data/listings.json to find the appropriate listing that matches the query provided by the input parameters.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): keywords describing the listing
- `size` (str): size string to filter the listing by (optional)
- `max_price` (float): maximum price (inclusive) allowed (optional)

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
Returns a list of matching listing objects, sorted by relevance. Returns an empty list if nothing matches.
**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
---
The agent will tell the user what to try differently and stops.

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Given a listing and the user's wardrobe, suggest 1-2 complete outfits.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): A listing dict that the user is considering buying
- `wardrobe` (dict): A wardrobe dict with the items field that contains a list of wardrobe item dicts.

**What it returns:**
<!-- Describe the return value -->
Returns a non-empty string with outfit suggestions from the LLM.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->

---
If the wardrobe is empty then the LLM uses general styling ideas.

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Generates a short outfit caption for the thrifted item.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): The outfit suggestion string returned from suggest_outfit().
- `new_item` (dict): The listing dict for the thrifted item.

**What it returns:**
<!-- Describe the return value -->
Returns a 2-4 sentence caption for the outfit.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->

---
If the outfit data is incomplete, it should return a descriptive error message string.

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**

The loop always runs the same three tools in the same order. There is no branching on *which* tool to call — only on whether to continue or stop early after each result. Here is the full decision tree:

**Step 1 — Parse the query.**
Send `query` to the LLM with a structured extraction prompt:

> "Extract the following fields from this shopping query. Return valid JSON only, no explanation.
> Fields: description (str — the item being searched for), size (str or null — clothing size if mentioned), max_price (float or null — maximum price if mentioned).
> Query: {query}"

Parse the JSON response to get `description`, `size`, and `max_price`. If the LLM returns malformed JSON, set `session["error"] = "Could not parse your query. Please try rephrasing."` and return the session early.

Store the parsed values as `session["parsed"] = {"description": ..., "size": ..., "max_price": ...}`.

**Step 2 — Call `search_listings()`.**
Pass `session["parsed"]["description"]`, `session["parsed"]["size"]`, `session["parsed"]["max_price"]`.
Store the returned list in `session["search_results"]`.

- **Branch A — empty list:** Set `session["error"]` to a message that echoes back what was searched, e.g. `"No listings found for 'vintage graphic tee'. Try broader keywords, a higher price limit, or remove the size filter."` Then `return session` immediately. `suggest_outfit` and `create_fit_card` are never called.
- **Branch B — one or more results:** Set `session["selected_item"] = session["search_results"][0]` (the highest-scored item, already sorted by `search_listings`) and continue.

**Step 3 — Call `suggest_outfit()`.**
Pass `session["selected_item"]` as `new_item` and `session["wardrobe"]` as `wardrobe`.
Store the returned string in `session["outfit_suggestion"]`.

- **Guard — empty string returned:** If `session["outfit_suggestion"].strip() == ""` (should not happen per tool spec, but guard anyway), set `session["error"] = "Could not generate outfit suggestions."` and `return session`.
- Otherwise continue.

**Step 4 — Call `create_fit_card()`.**
Pass `session["outfit_suggestion"]` as `outfit` and `session["selected_item"]` as `new_item`.
Store the returned string in `session["fit_card"]`.
No early-exit here — `create_fit_card` handles its own error case by returning an error string rather than raising, so whatever it returns gets stored and surfaced to the caller via `session["fit_card"]`.

**Return `session`.**

The loop knows it is done when it either hits a `return session` early-exit (Branch A or the guard) or falls off the end after Step 4. Callers check `session["error"]` first — `None` means success, a string means the interaction ended early.

---

## State Management

**How does information from one tool get passed to the next?**

The `session` dict is the single source of truth. Nothing is stored in global variables or function-level locals that outlive a single step. Here is what is tracked and how it flows:

| Session key | Written by | Read by | What it contains |
| ----------- | ---------- | ------- | ---------------- |
| `session["query"]` | `_new_session()` at init | Step 1 (parser) | The raw user query string |
| `session["parsed"]` | Step 1 (parser) | Step 2 (search_listings call) | Dict with keys `description` (str), `size` (str or None), `max_price` (float or None) |
| `session["search_results"]` | Step 2 | Step 2 branch logic | Full list of matching listing dicts, sorted best-first |
| `session["selected_item"]` | Step 2 Branch B | Steps 3 and 4 | The single listing dict passed into both `suggest_outfit` and `create_fit_card` |
| `session["wardrobe"]` | `_new_session()` at init | Step 3 | The wardrobe dict passed in by the caller; never modified |
| `session["outfit_suggestion"]` | Step 3 | Step 4 | The full outfit suggestion string from `suggest_outfit` |
| `session["fit_card"]` | Step 4 | Caller / UI | The final caption string from `create_fit_card` |
| `session["error"]` | Any early-exit branch | Caller / UI | `None` on success; a human-readable error string on early termination |

Each step reads only what it needs from the session and writes only its own output key — no step reaches back to overwrite a prior step's output. If `session["error"]` is set, all subsequent output keys remain `None`.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Set `session["error"] = "No listings found for '{description}'. Try broader keywords, a higher price limit, or remove the size filter."` and return the session immediately. `suggest_outfit` and `create_fit_card` are never called. `session["outfit_suggestion"]` and `session["fit_card"]` remain `None`. |
| suggest_outfit | Wardrobe is empty | The tool itself handles this: it detects `wardrobe["items"] == []` and calls the LLM with a general styling prompt ("what pairs well with this item in terms of style and vibe") instead of referencing specific wardrobe pieces. No error is set in the session; the string it returns is non-empty and the loop continues normally to `create_fit_card`. |
| create_fit_card | Outfit input is missing or incomplete | The tool guards `outfit.strip() == ""` at its top and returns a descriptive error string like `"Error: outfit data is missing — cannot generate a fit card."` The agent stores this string in `session["fit_card"]` without raising. `session["error"]` is left `None` because the tool itself communicated the problem in its return value. |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

```text
User query
    │
    ▼
Planning Loop (run_agent) ──────────────────────────────────────────────────────┐
    │                                                                           │
    ├─► [LLM] parse query → {description, size, max_price}                     │
    │       │                                                                   │
    │       │ malformed JSON                                                    │
    │       ├──────────────────► [ERROR] "Could not parse query" ───────────────┤
    │       │                                                                   │
    │       │ {description, size, max_price}                                    │
    │       ▼                                                                   │
    │   session["parsed"] = {description, size, max_price}                     │
    │       │                                                                   │
    ├─► search_listings(description, size, max_price)                          │
    │       │                                                                   │
    │       │ results = []                                                      │
    │       ├──────────────────► [ERROR] "No listings found..." ────────────────┤
    │       │                                                                   │  all error paths
    │       │ results = [item, ...]                                             │  return session
    │       ▼                                                                   │  with error set
    │   session["search_results"] = [...]                                       │
    │   session["selected_item"]  = results[0]                                 │
    │       │                                                                   │
    ├─► suggest_outfit(selected_item, wardrobe)                                │
    │       │                                                                   │
    │       ├─ wardrobe empty ──► [LLM] general styling advice                 │
    │       └─ wardrobe items ──► [LLM] wardrobe-specific outfit combos        │
    │               │                                                           │
    │               │ result = "" (guard)                                       │
    │               ├──────────────────► [ERROR] "Could not generate..." ───────┤
    │               │                                                           │
    │               │ result = outfit string                                    │
    │               ▼                                                           │
    │   session["outfit_suggestion"] = "..."                                    │
    │       │                                                                   │
    └─► create_fit_card(outfit_suggestion, selected_item)                      │
            │  [LLM] caption generation                                        │
            │  (returns error string if outfit empty — never raises)           │
            ▼                                                                   │
    session["fit_card"] = "..."                                                 │
            │                                                                   │
            ▼                                                                   │
        return session ◄────────────────────────────────────────────────────────┘
            │
    ┌───────┴─────────────┐
    │ error = None        │ error = "..."
    ▼                     ▼
show fit_card         show error message
```

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**
I will give Calude my planning.md, tools.py, agent.py, and data_loader.py. I'll ask it to implement the searching_listings, suggest_outfit, and create_fit_card. I expect it to produce the appropriate procedure following the steps in outlined for that function. I will very it by writing and running test queries.

**Milestone 4 — Planning loop and state management:**
I will give Claude my planning.md, tools.py, agent.py, and app.py. I'll ask it to implement run_agent() and handle_query(). I expect it to produce the appropriate code for run_agent() and handle_query(). I will run tests on run_agent() and handle_query().

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->
The agent will decipher the keywords, max_price, and size from the query. Then it will pass the extracted information into the session dict parameters and call the search_listings tool.

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->
search_listings tool should return a list of items sorted by their relevance. The agent will pick the most relevant item and call the suggest_outfit tool for that item and their wardrobe.

**Step 3:**
<!-- Continue until the full interaction is complete -->
suggest_outfit tool returns a string with 1-2 complete outfits for that item using their wardrobe. Then the agent calls create_fit_card that generates an short outfit caption for their thrifted find.

**Final output to user:**
<!-- What does the user actually see at the end? -->
The short caption for their thrifted find is the output that the user actually sees at the end.
