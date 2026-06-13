"""Unit tests for the daily Limited Time Sale pipeline.

Covers the pure logic in fetch_daily_deals.py (badge parsing, discount math,
ranking, catalog row swap) and post_daily.select_deal_pool (freshness window,
deal-score ordering, caption deal line).
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetch_daily_deals import (  # noqa: E402
    Deal,
    compute_discount_pct,
    deal_score,
    merge_deals_into_rows,
    parse_sales_volume,
    truncate_title,
)
import post_daily  # noqa: E402


# ─── parse_sales_volume ──────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("10K+ bought in past month", 10_000),
        ("400+ bought in past month", 400),
        ("1k+ bought in past month", 1_000),
        ("2M+ bought in past month", 2_000_000),
        ("1.5K+ bought in past month", 1_500),
        ("no badge here", 0),
        ("", 0),
        (None, 0),
        (1234, 0),
    ],
)
def test_parse_sales_volume(raw, expected):
    assert parse_sales_volume(raw) == expected


# ─── discount + score ────────────────────────────────────────────────────────

@pytest.mark.unit
def test_compute_discount_pct():
    assert compute_discount_pct(75.0, 100.0) == 25
    assert compute_discount_pct(89.99, 99.99) == 10
    assert compute_discount_pct(100.0, 100.0) == 0  # no markdown
    assert compute_discount_pct(100.0, 90.0) == 0   # "list" below price
    assert compute_discount_pct(0.0, 100.0) == 0    # missing price
    assert compute_discount_pct(50.0, 0.0) == 0     # missing list price


@pytest.mark.unit
def test_deal_score_prefers_badge_over_reviews():
    with_badge = deal_score(10_000, 500, 20)
    without_badge = deal_score(0, 50_000, 20)
    assert with_badge == 10_000 * 20
    assert without_badge == 5_000 * 20
    assert with_badge > without_badge


@pytest.mark.unit
def test_truncate_title_word_boundary():
    long = "Apple AirPods Pro 2 Wireless Earbuds Active Noise Cancellation Bluetooth Hi-Fi"
    out = truncate_title(long, limit=40)
    assert len(out) <= 40
    assert not out.endswith((" ", ",", "-"))
    assert truncate_title("Short name") == "Short name"


# ─── merge_deals_into_rows ───────────────────────────────────────────────────

FIELDS = [
    "Product Name", "Category", "Price Range", "Review Count", "Rating", "BSR",
    "Affiliate Potential", "Amazon URL", "Refreshed Date", "Action Needed",
]


def _deal(asin="B0TEST0001", title="Test Widget Pro", **kw) -> Deal:
    defaults = dict(
        category="Kitchen", price=39.99, list_price=59.99, discount_pct=33,
        bought_past_month=5000, rating=4.7, review_count=2500, bsr=3,
        image="", deal_score=165_000.0,
    )
    defaults.update(kw)
    return Deal(asin=asin, title=title, **defaults)


def _permanent_row(name="Existing Camera", asin="B0EXIST001"):
    return {
        "Product Name": name, "Category": "Photography", "Price Range": "299",
        "Review Count": "1200", "Rating": "4.8", "BSR": "#2",
        "Affiliate Potential": "9",
        "Amazon URL": f"https://www.amazon.com/dp/{asin}?tag=hotproduct033-20",
        "Refreshed Date": "6/1/2026", "Action Needed": "",
    }


@pytest.mark.unit
def test_merge_swaps_out_yesterdays_deals():
    yesterday_deal = {
        **_permanent_row(name="Old Deal", asin="B0OLDDEAL1"),
        "Temporary": "daily-deal", "Deal Date": "2026-06-09",
        "List Price": "50.00", "Discount %": "20", "Bought Past Month": "100",
    }
    rows = [_permanent_row(), yesterday_deal]
    out, fields = merge_deals_into_rows(rows, FIELDS + ["Temporary", "Deal Date",
                                        "List Price", "Discount %", "Bought Past Month"],
                                        [_deal()], "2026-06-10")
    names = [r["Product Name"] for r in out]
    assert "Old Deal" not in names           # yesterday's batch removed
    assert "Existing Camera" in names        # permanent row kept
    assert "Test Widget Pro" in names        # today's deal added
    new = next(r for r in out if r["Product Name"] == "Test Widget Pro")
    assert new["Temporary"] == "daily-deal"
    assert new["Deal Date"] == "2026-06-10"
    assert new["Discount %"] == "33"
    assert new["Bought Past Month"] == "5000"
    assert "tag=hotproduct033-20" in new["Amazon URL"]
    assert new["Refreshed Date"] == "6/10/2026"


@pytest.mark.unit
def test_merge_adds_deal_columns_to_legacy_fieldnames():
    out, fields = merge_deals_into_rows([_permanent_row()], FIELDS, [_deal()], "2026-06-10")
    for col in ("Temporary", "Deal Date", "List Price", "Discount %", "Bought Past Month"):
        assert col in fields


@pytest.mark.unit
def test_merge_marks_existing_catalog_row_instead_of_duplicating():
    rows = [_permanent_row(name="Existing Camera", asin="B0EXIST001")]
    deal = _deal(asin="B0EXIST001", title="Existing Camera Renamed", price=249.0)
    out, _ = merge_deals_into_rows(rows, FIELDS, [deal], "2026-06-10")
    assert len(out) == 1                      # no duplicate row
    row = out[0]
    assert row["Product Name"] == "Existing Camera"   # original name kept
    assert row["Temporary"] == ""                     # stays permanent
    assert row["Deal Date"] == "2026-06-10"
    assert row["Price Range"] == "249.00"             # price refreshed


@pytest.mark.unit
def test_merge_clears_stale_deal_columns_on_permanent_rows():
    stale = {**_permanent_row(), "Deal Date": "2026-06-08", "Discount %": "15",
             "List Price": "350", "Bought Past Month": "900", "Temporary": ""}
    out, _ = merge_deals_into_rows([stale], FIELDS + ["Temporary", "Deal Date",
                                   "List Price", "Discount %", "Bought Past Month"],
                                   [], "2026-06-10")
    assert out[0]["Deal Date"] == ""
    assert out[0]["Discount %"] == ""


# ─── post_daily.select_deal_pool ─────────────────────────────────────────────

def _pool_product(name, *, deal_date, discount=20, bought=1000, reviews=500):
    return {
        "name": name, "slug": name.lower().replace(" ", "-"), "category": "Kitchen",
        "temporary": "daily-deal", "deal_date": deal_date,
        "discount_pct": discount, "bought_past_month": bought,
        "review_count": reviews,
    }


@pytest.mark.unit
def test_select_deal_pool_filters_stale_and_ranks():
    today = date(2026, 6, 10)
    fresh_hot = _pool_product("Hot", deal_date="2026-06-10", discount=40, bought=10_000)
    fresh_mild = _pool_product("Mild", deal_date="2026-06-10", discount=10, bought=100)
    stale = _pool_product("Stale", deal_date="2026-06-01")
    not_deal = {**_pool_product("Regular", deal_date="2026-06-10"), "temporary": ""}
    no_date = _pool_product("NoDate", deal_date="")

    pool = post_daily.select_deal_pool(
        [fresh_mild, stale, fresh_hot, not_deal, no_date], today=today
    )
    assert [p["name"] for p in pool] == ["Hot", "Mild"]


@pytest.mark.unit
def test_select_deal_pool_rejects_yesterday_after_missed_refresh():
    today = date(2026, 6, 10)
    yesterday = _pool_product("Yesterday", deal_date="2026-06-09")
    cutoff = _pool_product("TooOld", deal_date=(today - timedelta(days=3)).isoformat())
    pool = post_daily.select_deal_pool([yesterday, cutoff], today=today)
    assert pool == []


@pytest.mark.unit
def test_instagram_body_includes_deal_line():
    product = {
        "name": "Test Widget Pro", "slug": "test-widget-pro", "category": "Kitchen",
        "price": "39.99", "rating": 4.7, "reviews": "2500",
        "discount_pct": 33, "list_price": "59.99",
    }
    body = post_daily.instagram_body(product)
    assert "33% OFF" in body
    assert "$59.99" in body


@pytest.mark.unit
def test_deal_pool_dedup_excludes_already_posted():
    """Simulates the main() dedup: select_deal_pool returns all fresh deals
    (it has no access to post_log), but filtering against posted_names
    removes any deal that was already posted in a prior run."""
    today = date(2026, 6, 10)
    already_posted = _pool_product("Hot", deal_date="2026-06-10", discount=40, bought=10_000)
    not_posted = _pool_product("Mild", deal_date="2026-06-10", discount=10, bought=100)

    pool = post_daily.select_deal_pool([already_posted, not_posted], today=today)
    assert len(pool) == 2  # select_deal_pool sees both (no post_log access)

    # Replicate the main() dedup step
    posted_names = {"Hot"}
    fresh = [p for p in pool if p["name"] not in posted_names]
    assert [p["name"] for p in fresh] == ["Mild"]


@pytest.mark.unit
def test_deal_pool_dedup_all_posted_returns_empty():
    """When every deal in the pool is already posted, fresh_deals is empty
    and main() falls back to the regular rotation."""
    today = date(2026, 6, 10)
    p1 = _pool_product("Alpha", deal_date="2026-06-10", discount=30, bought=5_000)
    p2 = _pool_product("Beta", deal_date="2026-06-10", discount=20, bought=3_000)

    pool = post_daily.select_deal_pool([p1, p2], today=today)
    posted_names = {"Alpha", "Beta"}
    fresh = [p for p in pool if p["name"] not in posted_names]
    assert fresh == []


@pytest.mark.unit
def test_instagram_body_no_deal_line_for_regular_products():
    product = {
        "name": "Regular Thing", "slug": "regular-thing", "category": "Kitchen",
        "price": "39.99", "rating": 4.7, "reviews": "2500",
    }
    assert "LIMITED-TIME DEAL" not in post_daily.instagram_body(product)
