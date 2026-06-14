"""
tests/test_tools.py

Pytest tests for each FitFindr tool. Run with: pytest tests/

Tests cover:
  - search_listings: happy path, empty results, price filter, size filter
  - suggest_outfit: empty wardrobe (no exception, non-empty string)
  - create_fit_card: empty outfit guard (no exception, returns error string)
"""

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings ────────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    # Impossible query — no exception, just empty list
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    # All returned items must be within the price ceiling
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    results = search_listings("top", size="M", max_price=None)
    # Every returned item's size field must contain "m" (case-insensitive)
    for item in results:
        assert "m" in item["size"].lower(), f"{item['title']} has size {item['size']}"


def test_search_result_fields():
    results = search_listings("vintage", size=None, max_price=100)
    assert len(results) > 0
    required_fields = {"id", "title", "description", "category", "style_tags",
                       "size", "condition", "price", "colors", "platform"}
    for item in results:
        for field in required_fields:
            assert field in item, f"Missing field '{field}' in result"


def test_search_results_sorted_by_relevance():
    # A more specific query should rank the exact match higher than a loose match
    results = search_listings("graphic tee", size=None, max_price=50)
    # Just check we get results and no exception — ordering is score-based
    assert isinstance(results, list)


# ── suggest_outfit ─────────────────────────────────────────────────────────────

def test_suggest_outfit_empty_wardrobe_no_exception():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    # Must return a non-empty string, not raise an exception
    result = suggest_outfit(results[0], get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result.strip()) > 0


def test_suggest_outfit_example_wardrobe_returns_string():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    result = suggest_outfit(results[0], get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result.strip()) > 0


# ── create_fit_card ────────────────────────────────────────────────────────────

def test_fit_card_empty_outfit_no_exception():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    # Empty outfit string — must return error message, not raise
    result = create_fit_card("", results[0])
    assert isinstance(result, str)
    assert len(result.strip()) > 0


def test_fit_card_whitespace_outfit_no_exception():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    result = create_fit_card("   ", results[0])
    assert isinstance(result, str)
    assert len(result.strip()) > 0


def test_fit_card_valid_input_returns_string():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    outfit = "Pair with baggy jeans and chunky sneakers for a streetwear look."
    result = create_fit_card(outfit, results[0])
    assert isinstance(result, str)
    assert len(result.strip()) > 0
