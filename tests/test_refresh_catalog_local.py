"""Unit tests for refresh_catalog_local decision logic (pure functions)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from amazon_local_api import ProductData  # noqa: E402
from refresh_catalog_local import decide_update, extract_asin, unverified_removal_reason  # noqa: E402


def make_row(price="100.00", rating="4.5", reviews="200"):
    return {
        "Product Name": "Test Product",
        "Price Range": price,
        "Rating": rating,
        "Review Count": reviews,
        "Amazon URL": "https://www.amazon.com/dp/B0TEST00AA?tag=x-20",
    }


def make_product(price=100.0, rating=4.5, reviews=200, status="ok"):
    return ProductData(
        asin="B0TEST00AA", title="Test Product", price=price, rating=rating,
        reviews_count=reviews, availability="In Stock", is_in_stock=True,
        page_status=status,
    )


class TestExtractAsin:
    def test_dp_url(self):
        assert extract_asin("https://www.amazon.com/dp/B0DW1X5YCQ?tag=t-20") == "B0DW1X5YCQ"

    def test_gp_product_url(self):
        assert extract_asin("https://www.amazon.com/gp/product/B0DW1X5YCQ") == "B0DW1X5YCQ"

    def test_no_asin(self):
        assert extract_asin("https://example.com") is None


class TestDecideUpdate:
    def test_within_tolerance_no_update(self):
        d = decide_update(make_row(), make_product(price=101.0, rating=4.5, reviews=205))
        assert d.fields == {}

    def test_price_change_above_tolerance(self):
        d = decide_update(make_row(), make_product(price=110.0))
        assert d.fields["Price Range"] == "110.00"

    def test_price_drift_above_ceiling_skipped(self):
        d = decide_update(make_row(), make_product(price=200.0))  # +100%
        assert "Price Range" not in d.fields
        assert d.suspicious_price is True

    def test_rating_change(self):
        d = decide_update(make_row(), make_product(rating=4.2))
        assert d.fields["Rating"] == "4.2"

    def test_reviews_change_above_tolerance(self):
        d = decide_update(make_row(), make_product(reviews=300))
        assert d.fields["Review Count"] == "300"

    def test_missing_live_fields_never_clear_csv(self):
        d = decide_update(make_row(), make_product(price=None, rating=None, reviews=None))
        assert d.fields == {}

    def test_empty_csv_price_gets_filled(self):
        d = decide_update(make_row(price=""), make_product(price=55.5))
        assert d.fields["Price Range"] == "55.50"

    def test_row_not_mutated(self):
        row = make_row()
        snapshot = dict(row)
        decide_update(row, make_product(price=110.0))
        assert row == snapshot


class TestUnverifiedRemovalReason:
    def test_verified_price_kept(self):
        live = make_product(price=100.0)
        decision = decide_update(make_row(), live)
        assert unverified_removal_reason(live, decision) is None

    def test_suspicious_price_removed(self):
        live = make_product(price=200.0)
        decision = decide_update(make_row(), live)
        assert unverified_removal_reason(live, decision) == "suspicious_price"

    def test_no_live_price_removed(self):
        live = make_product(price=None, rating=4.5, reviews=100)
        assert unverified_removal_reason(live, decide_update(make_row(), live)) == "no_live_price"

    def test_no_buybox_removed(self):
        live = ProductData(
            asin="B0TEST00AA", title="Test", page_status="ok",
            availability="See All Buying Options", rating=4.5, reviews_count=10,
        )
        assert unverified_removal_reason(live) == "no_buybox_offer"

    def test_listing_removed(self):
        live = make_product(status="not_found")
        assert unverified_removal_reason(live) == "listing_removed"

    def test_scrape_blocked_removed(self):
        live = make_product(status="blocked")
        assert unverified_removal_reason(live) == "scrape_blocked"

    def test_unavailable_removed(self):
        live = ProductData(
            asin="B0TEST00AA", title="Test", page_status="ok",
            availability="Currently unavailable.", is_in_stock=False,
            rating=4.0, reviews_count=50,
        )
        assert unverified_removal_reason(live) == "unavailable"
