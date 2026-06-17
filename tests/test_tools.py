from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

# ── Shared fixture ────────────────────────────────────────────────────────────

SAMPLE_ITEM = {
    "id": "lst_002",
    "title": "Y2K Baby Tee — Butterfly Print",
    "description": "Super cute early 2000s baby tee with butterfly graphic.",
    "category": "tops",
    "style_tags": ["y2k", "vintage", "graphic tee"],
    "size": "S/M",
    "condition": "excellent",
    "price": 18.00,
    "colors": ["white", "pink"],
    "brand": None,
    "platform": "depop",
}

# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []   # empty list, no exception

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)

def test_search_size_filter():
    results = search_listings("jeans denim", size="M", max_price=None)
    assert all("m" in item["size"].lower() for item in results)

def test_search_best_match_first():
    results = search_listings("vintage graphic tee", size=None, max_price=None)
    assert len(results) > 1
    # First result must mention more of the keywords than the last
    first_title = results[0]["title"].lower() + " " + " ".join(results[0]["style_tags"])
    last_title  = results[-1]["title"].lower() + " " + " ".join(results[-1]["style_tags"])
    assert sum(w in first_title for w in ["vintage", "graphic", "tee"]) >= \
           sum(w in last_title  for w in ["vintage", "graphic", "tee"])

# ── suggest_outfit ────────────────────────────────────────────────────────────

def test_suggest_outfit_empty_wardrobe():
    # Should return general styling advice, not crash
    result = suggest_outfit(SAMPLE_ITEM, get_empty_wardrobe())
    print(f"\n[suggest_outfit / empty wardrobe]\n{result}")
    assert isinstance(result, str)
    assert len(result.strip()) > 100  # must be a substantive response, not a one-liner
    # Should mention something about the item
    assert any(word in result.lower() for word in ["tee", "butterfly", "y2k", "top", "shirt"])

def test_suggest_outfit_with_wardrobe():
    result = suggest_outfit(SAMPLE_ITEM, get_example_wardrobe())
    print(f"\n[suggest_outfit / with wardrobe]\n{result}")
    assert isinstance(result, str)
    assert len(result.strip()) > 100
    # With a real wardrobe the LLM should reference specific pieces — check for at least one
    wardrobe_names = [item["name"].lower() for item in get_example_wardrobe()["items"]]
    any_piece_mentioned = any(
        any(word in result.lower() for word in name.split())
        for name in wardrobe_names
    )
    assert any_piece_mentioned, "Response should reference at least one wardrobe piece by name"

# ── create_fit_card ───────────────────────────────────────────────────────────

def test_create_fit_card_empty_outfit():
    # Must return an error string — not raise
    result = create_fit_card("", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert "error" in result.lower() or "missing" in result.lower()

def test_create_fit_card_whitespace_outfit():
    result = create_fit_card("   ", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result) > 0

def test_create_fit_card_returns_string():
    outfit = (
        "Pair the butterfly tee with baggy dark-wash jeans and chunky sneakers "
        "for an easy Y2K streetwear look."
    )
    result = create_fit_card(outfit, SAMPLE_ITEM)
    print(f"\n[create_fit_card]\n{result}")
    assert isinstance(result, str)
    assert len(result.strip()) > 0
    # Spec requires item name, price, and platform to each appear once
    assert "depop" in result.lower(), "Caption must mention the platform"
    assert "18" in result, "Caption must mention the price"
    assert any(w in result.lower() for w in ["butterfly", "tee", "baby tee"]), \
        "Caption must mention the item name"
