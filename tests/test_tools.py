"""
tests/test_tools.py — FitFindr v2

Tests cover:
  - validate_query: fashion queries pass, off-topic queries are rejected
  - search_ebay: live results, price filter, size filter (skipped without eBay creds)
  - suggest_outfit: empty wardrobe, example wardrobe, with style_goal
  - create_fit_card: empty outfit guard, valid input
"""

import os
import pytest

from tools import validate_query, search_ebay, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

# ── Shared mock item (avoids eBay dependency in outfit/fitcard tests) ──────────

_MOCK_ITEM = {
    "id":          "test_001",
    "title":       "Vintage Levi's 501 Jeans",
    "description": "Classic medium-wash denim in great condition.",
    "category":    "bottoms",
    "style_tags":  ["vintage", "denim"],
    "size":        "W30 L30",
    "condition":   "Good",
    "price":       35.00,
    "colors":      ["blue", "indigo"],
    "brand":       "Levi's",
    "platform":    "eBay",
    "image_url":   "",
    "item_url":    "https://www.ebay.com/itm/example",
}

_HAS_EBAY = bool(os.environ.get("EBAY_CLIENT_ID") and os.environ.get("EBAY_CLIENT_SECRET"))
_ebay_skip = pytest.mark.skipif(not _HAS_EBAY, reason="EBAY_CLIENT_ID/SECRET not set")


# ── validate_query ─────────────────────────────────────────────────────────────

def test_validate_fashion_query_passes():
    result = validate_query("vintage graphic tee under $30")
    assert result["valid"] is True
    assert result["warning"] is None


def test_validate_aesthetic_query_passes():
    result = validate_query("dark academia outfit for fall")
    assert result["valid"] is True


def test_validate_adjective_query_passes():
    # "sexy", "edgy", etc. are valid fashion descriptors and must not be rejected
    result = validate_query("sexy little black dress")
    assert result["valid"] is True


def test_validate_occasion_query_passes():
    result = validate_query("something to wear to a music festival")
    assert result["valid"] is True


def test_validate_off_topic_rejected():
    result = validate_query("how do I make pasta carbonara")
    assert result["valid"] is False
    assert result["warning"] is not None
    assert len(result["warning"]) > 0


def test_validate_tech_query_rejected():
    result = validate_query("explain how machine learning works")
    assert result["valid"] is False


def test_validate_returns_dict_structure():
    result = validate_query("vintage tee")
    assert "valid" in result
    assert "warning" in result


# ── search_ebay ───────────────────────────────────────────────────────────────

@_ebay_skip
def test_search_ebay_returns_results():
    results = search_ebay("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


@_ebay_skip
def test_search_ebay_result_fields():
    results = search_ebay("jeans", size=None, max_price=None)
    assert len(results) > 0
    required = {"id", "title", "description", "category", "style_tags",
                "size", "condition", "price", "colors", "platform",
                "image_url", "item_url"}
    for item in results:
        for field in required:
            assert field in item, f"Missing field '{field}' in eBay result"


@_ebay_skip
def test_search_ebay_price_filter():
    results = search_ebay("shirt", size=None, max_price=20)
    assert all(item["price"] <= 20 for item in results), (
        "Price filter returned item above max_price"
    )


@_ebay_skip
def test_search_ebay_with_style_goal():
    results = search_ebay("cardigan", size=None, max_price=None, style_goal="dark academia")
    assert isinstance(results, list)


@_ebay_skip
def test_search_ebay_empty_on_impossible_query():
    # Price ceiling so low it should return nothing or an empty list — must not raise
    results = search_ebay("designer ballgown", size=None, max_price=1)
    assert isinstance(results, list)


# ── suggest_outfit ─────────────────────────────────────────────────────────────

def test_suggest_outfit_empty_wardrobe():
    result = suggest_outfit(_MOCK_ITEM, get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result.strip()) > 0


def test_suggest_outfit_example_wardrobe():
    result = suggest_outfit(_MOCK_ITEM, get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result.strip()) > 0


def test_suggest_outfit_with_style_goal():
    result = suggest_outfit(_MOCK_ITEM, get_empty_wardrobe(), style_goal="dark academia")
    assert isinstance(result, str)
    assert len(result.strip()) > 0


# ── create_fit_card ────────────────────────────────────────────────────────────

def test_fit_card_empty_outfit_guard():
    result = create_fit_card("", _MOCK_ITEM)
    assert isinstance(result, str)
    assert len(result.strip()) > 0


def test_fit_card_whitespace_outfit_guard():
    result = create_fit_card("   ", _MOCK_ITEM)
    assert isinstance(result, str)
    assert len(result.strip()) > 0


def test_fit_card_valid_input():
    outfit = "Pair with straight-leg jeans and white sneakers for a clean casual look."
    result = create_fit_card(outfit, _MOCK_ITEM)
    assert isinstance(result, str)
    assert len(result.strip()) > 0
