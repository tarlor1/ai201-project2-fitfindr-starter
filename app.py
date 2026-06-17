"""
app.py

Gradio interface for FitFindr. The layout and wiring are already set up —
your job is to fill in handle_query() so it calls run_agent() and maps
the session results to the three output panels.

Run with:
    python app.py

Then open the localhost URL shown in your terminal (usually http://localhost:7860,
but check your terminal — the port may differ).
"""

import gradio as gr

from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── query handler ─────────────────────────────────────────────────────────────

def handle_query(user_query: str, wardrobe_choice: str) -> tuple[str, str, str, str]:
    """
    Called by Gradio when the user submits a query.

    Args:
        user_query:     The text the user typed into the search box.
        wardrobe_choice: Either "Example wardrobe" or "Empty wardrobe (new user)".

    Returns:
        A tuple of four strings:
            (listing_text, outfit_suggestion, fit_card, tool_log)
        Each string maps to one of the four output panels in the UI.
    """
    log = []

    def skip(name: str) -> None:
        log.append(f"  {name:<20} skipped")

    # Step 1: guard empty query
    if not user_query or not user_query.strip():
        return "Please enter a search query.", "", "", ""

    # Step 2: select wardrobe
    wardrobe = (
        get_example_wardrobe()
        if wardrobe_choice == "Example wardrobe"
        else get_empty_wardrobe()
    )

    # Step 3: run agent
    session = run_agent(query=user_query, wardrobe=wardrobe)

    # Build log from what the session contains
    parsed = session.get("parsed") or {}
    log.append(
        f"[OK] parse_query        -> description={parsed.get('description')!r}, "
        f"size={parsed.get('size')!r}, max_price={parsed.get('max_price')!r}"
    )

    results = session.get("search_results") or []
    if results:
        log.append(
            f"[OK] search_listings    -> {len(results)} result(s), "
            f"selected \"{session['selected_item']['title']}\""
        )
    else:
        log.append(f"[--] search_listings    -> 0 results — stopping here")
        skip("suggest_outfit")
        skip("create_fit_card")
        return session["error"], "", "", "\n".join(log)

    if session.get("outfit_suggestion"):
        wardrobe_label = "empty wardrobe" if not wardrobe["items"] else "wardrobe items"
        log.append(f"[OK] suggest_outfit     -> outfit generated (used {wardrobe_label})")
    else:
        log.append(f"[--] suggest_outfit     -> returned empty — stopping here")
        skip("create_fit_card")
        return session["error"], "", "", "\n".join(log)

    if session.get("fit_card"):
        log.append(f"[OK] create_fit_card    -> caption ready")
    else:
        log.append(f"[--] create_fit_card    -> no output")

    # Step 5: format listing
    item = session["selected_item"]
    listing_text = (
        f"{item['title']}\n\n"
        f"Price:      ${item['price']:.2f}\n"
        f"Size:       {item['size']}\n"
        f"Condition:  {item['condition']}\n"
        f"Platform:   {item['platform']}\n"
        f"Tags:       {', '.join(item['style_tags'])}\n\n"
        f"{item['description']}"
    )

    return listing_text, session["outfit_suggestion"], session["fit_card"], "\n".join(log)


# ── interface ─────────────────────────────────────────────────────────────────

EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "90s track jacket in size M",
    "flowy midi skirt under $40",
    "black combat boots size 8",
    "designer ballgown size XXS under $5",   # deliberate no-results test
]

def build_interface():
    with gr.Blocks(title="FitFindr") as demo:
        gr.Markdown("""
# FitFindr 🛍️
Find secondhand pieces and get outfit ideas based on your wardrobe.
Describe what you're looking for — include size and price if you want to filter.
        """)

        with gr.Row():
            query_input = gr.Textbox(
                label="What are you looking for?",
                placeholder="e.g. vintage graphic tee under $30, size M",
                lines=2,
                scale=3,
            )
            wardrobe_choice = gr.Radio(
                choices=["Example wardrobe", "Empty wardrobe (new user)"],
                value="Example wardrobe",
                label="Wardrobe",
                scale=1,
            )

        submit_btn = gr.Button("Find it", variant="primary")

        with gr.Row():
            listing_output = gr.Textbox(
                label="🛍️ Top listing found",
                lines=8,
                interactive=False,
            )
            outfit_output = gr.Textbox(
                label="👗 Outfit idea",
                lines=8,
                interactive=False,
            )
            fitcard_output = gr.Textbox(
                label="✨ Your fit card",
                lines=8,
                interactive=False,
            )

        tool_log_output = gr.Textbox(
            label="🔧 Tools run",
            lines=4,
            interactive=False,
        )

        gr.Examples(
            examples=[[q, "Example wardrobe"] for q in EXAMPLE_QUERIES],
            inputs=[query_input, wardrobe_choice],
            label="Try these queries",
        )

        outputs = [listing_output, outfit_output, fitcard_output, tool_log_output]

        submit_btn.click(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=outputs,
        )
        query_input.submit(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=outputs,
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch()
