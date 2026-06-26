"""Unit tests for amazon_local_api — the local Oxylabs-equivalent scraper.

Parser tests use compact HTML fixtures built from real Amazon markup
(captured 2026-06-10). No network access required.

Run:  venv/bin/python -m pytest tests/test_amazon_local_api.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from amazon_local_api import (  # noqa: E402
    ProductData,
    classify_page,
    parse_product,
    parse_price_string,
)


# ── Fixture HTML (real markup shapes from live amazon.com pages) ────────────

TITLE_HTML = """
<span id="productTitle" class="a-size-large product-title-word-break">
  ASUS ROG Strix G16 (2025) Gaming Laptop, 16" ROG Nebula Display
</span>
"""

TWISTER_JSON_HTML = """
<div id="twister-plus-buying-options-price-data" class="aok-hidden twister-plus-buying-options-price-data">
{"desktop_buybox_group_1":[{"displayPrice":"$2,570.00","priceAmount":2570.00,"currencySymbol":"$","integerValue":"2,570","decimalSeparator":".","fractionalValue":"00","symbolPosition":"left","buyingOptionType":"NEW","aapiBuyingOptionIndex":0}]}
</div>
"""

OFFSCREEN_PRICE_HTML = """
<div id="corePrice_feature_div">
  <span class="a-price" data-a-size="xl"><span class="a-offscreen">$129.99</span>
  <span aria-hidden="true"><span class="a-price-symbol">$</span><span class="a-price-whole">129<span class="a-price-decimal">.</span></span><span class="a-price-fraction">99</span></span></span>
</div>
"""

# Current Amazon quirk: buy-box offscreen span is EMPTY (just &nbsp;); the
# real price only exists in the aria-hidden whole/fraction parts.
EMPTY_OFFSCREEN_PARTS_HTML = """
<div id="apex_offerDisplay_desktop">
  <span class="a-price aok-align-center priceToPay apex-pricetopay-value" data-a-size="xl">
    <span class="a-offscreen">&nbsp;</span>
    <span aria-hidden="true"><span class="a-price-symbol">$</span><span class="a-price-whole">2,570<span class="a-price-decimal">.</span></span><span class="a-price-fraction">00</span></span>
  </span>
</div>
"""

# A comparison-carousel price that must NOT be picked over buy-box sources.
CAROUSEL_TRAP_HTML = """
<div id="HLCXComparisonWidget_feature_div">
  <span class="a-price"><span class="a-offscreen">$9.99</span></span>
</div>
"""

RATING_HTML = """
<span id="acrPopover" class="reviewCountTextLinkedHistogram noUnderline" title="4.4 out of 5 stars">
  <i class="a-icon a-icon-star a-star-4-5"><span class="a-icon-alt">4.4 out of 5 stars</span></i>
</span>
"""

RATING_ALT_ONLY_HTML = """
<i class="a-icon a-icon-star a-star-4-5"><span class="a-icon-alt">4.7 out of 5 stars</span></i>
"""

REVIEWS_ARIA_HTML = """
<span id="acrCustomerReviewText" aria-label="172 Reviews" class="a-size-small">(172)</span>
"""

REVIEWS_RATINGS_TEXT_HTML = """
<span id="acrCustomerReviewText" class="a-size-base">12,345 ratings</span>
"""

AVAILABILITY_IN_STOCK_HTML = """
<div id="availability" class="a-section">
  <span class="a-size-medium a-color-success primary-availability-message"> In Stock </span>
</div>
"""

AVAILABILITY_UNAVAILABLE_HTML = """
<div id="availability" class="a-section">
  <span class="a-size-medium a-color-price">Currently unavailable.</span>
</div>
"""

BSR_HTML = """
<th class="a-color-secondary a-size-base prodDetSectionEntry"> Best Sellers Rank </th>
<td><span><ul class="a-unordered-list a-nostyle a-vertical">
<li><span class="a-list-item"><span>#217 in Computers &amp; Accessories (<a href="/gp/bestsellers/pc">See Top 100</a>)</span></span></li>
<li><span class="a-list-item"><span>#16 in Traditional Laptop Computers</span></span></li>
</ul></span></td>
"""

CAPTCHA_HTML = """
<html><body>
<h4>Type the characters you see in this image:</h4>
<p>Sorry, we just need to make sure you're not a robot.</p>
<form action="/errors/validateCaptcha"></form>
</body></html>
"""

# No-buy-box listing: availability block only contains the All Offers
# Display spinner ("See All Buying Options"). Price is genuinely absent.
NO_OFFER_HTML = """
<div id="availability" class="a-section">
  <div id="all-offers-display" class="a-section">
    <div id="all-offers-display-spinner" class="a-spinner-wrapper"></div>
  </div>
</div>
"""

DOG_PAGE_HTML = """
<html><body><img src="https://images-na.ssl-images-amazon.com/images/G/01/error/500_503.png"
alt="Sorry! Something went wrong on our end."/><a href="/dogsofamazon">Dogs of Amazon</a></body></html>
"""

# 2026-06-10 catalog corruption: buy-box empty, star rating rendered with
# a-price-whole/fraction inside apex_offerDisplay_desktop (AirPods Max).
RATING_AS_PRICE_HTML = """
<div id="apex_offerDisplay_desktop">
  <span class="a-price aok-align-center priceToPay apex-pricetopay-value" data-a-size="xl">
    <span class="a-offscreen">&nbsp;</span>
    <span aria-hidden="true"><span class="a-price-symbol">$</span>
    <span class="a-price-whole">4<span class="a-price-decimal">.</span></span>
    <span class="a-price-fraction">6</span></span>
  </span>
</div>
<span id="acrPopover" title="4.6 out of 5 stars">
  <i class="a-icon a-icon-star"><span class="a-icon-alt">4.6 out of 5 stars</span></i>
</span>
<span id="acrCustomerReviewText" aria-label="16,685 ratings">(16,685)</span>
"""


# Strikethrough "List Price" markup — the markdown reference (must outrank the
# current buy-box price, which lives in priceToPay, not a-text-price).
LIST_PRICE_HTML = """
<div id="corePriceDisplay_desktop_feature_div">
  <span class="a-price a-text-price" data-a-strike="true" data-a-color="secondary">
    <span class="a-offscreen">$199.99</span><span aria-hidden="true">$199.99</span>
  </span>
</div>
"""

# "1K+ bought in past month" social-proofing badge (sales-velocity signal).
BOUGHT_BADGE_HTML = """
<div id="social-proofing-faceout-title">
  <span id="social-proofing-faceout-title-tk_bought" class="a-text-bold">1K+ bought in past month</span>
</div>
"""


def full_page(*parts: str) -> str:
    return "<html><body>" + "".join(parts) + "</body></html>"


GOOD_PAGE = full_page(
    TITLE_HTML, CAROUSEL_TRAP_HTML, TWISTER_JSON_HTML, EMPTY_OFFSCREEN_PARTS_HTML,
    RATING_HTML, REVIEWS_ARIA_HTML, AVAILABILITY_IN_STOCK_HTML, BSR_HTML,
)


# ── parse_price_string ───────────────────────────────────────────────────────

class TestParsePriceString:
    def test_dollar_with_thousands(self):
        assert parse_price_string("$2,570.00") == 2570.0

    def test_plain_number(self):
        assert parse_price_string("129.99") == 129.99

    def test_range_takes_low_end(self):
        assert parse_price_string("$19.99 - $29.99") == 19.99

    def test_garbage_returns_none(self):
        assert parse_price_string("See price in cart") is None

    def test_empty_returns_none(self):
        assert parse_price_string("") is None
        assert parse_price_string("\xa0") is None

    def test_rejects_star_rating_text(self):
        assert parse_price_string("4.6 out of 5 stars") is None
        assert parse_price_string("4.4 out of 5 stars") is None

    def test_rejects_bare_review_count(self):
        assert parse_price_string("(16,685)") is None
        assert parse_price_string("16,685 ratings") is None

    def test_broad_fallback_requires_currency(self):
        assert parse_price_string("129.99", require_currency=True) is None
        assert parse_price_string("$129.99", require_currency=True) == 129.99


# ── classify_page ────────────────────────────────────────────────────────────

class TestClassifyPage:
    def test_good_page(self):
        assert classify_page(GOOD_PAGE, 200) == "ok"

    def test_captcha(self):
        assert classify_page(CAPTCHA_HTML, 200) == "blocked"

    def test_dog_page(self):
        assert classify_page(DOG_PAGE_HTML, 200) == "server_error"

    def test_http_404(self):
        assert classify_page("<html></html>", 404) == "not_found"

    def test_http_503(self):
        assert classify_page("anything", 503) == "server_error"

    def test_no_title_is_suspect(self):
        assert classify_page(full_page(AVAILABILITY_IN_STOCK_HTML), 200) == "suspect"


# ── parse_product field extraction ───────────────────────────────────────────

class TestParseProduct:
    def test_title(self):
        p = parse_product(GOOD_PAGE, asin="B0TEST00AA")
        assert p.title.startswith("ASUS ROG Strix G16")

    def test_price_prefers_twister_json_over_carousel(self):
        p = parse_product(GOOD_PAGE, asin="B0TEST00AA")
        assert p.price == 2570.0
        assert p.currency == "USD"

    def test_price_from_offscreen_selector(self):
        page = full_page(TITLE_HTML, OFFSCREEN_PRICE_HTML)
        p = parse_product(page, asin="B0TEST00AA")
        assert p.price == 129.99

    def test_price_assembled_from_parts_when_offscreen_empty(self):
        page = full_page(TITLE_HTML, EMPTY_OFFSCREEN_PARTS_HTML)
        p = parse_product(page, asin="B0TEST00AA")
        assert p.price == 2570.0

    def test_carousel_price_not_used_as_buybox(self):
        page = full_page(TITLE_HTML, CAROUSEL_TRAP_HTML, EMPTY_OFFSCREEN_PARTS_HTML)
        p = parse_product(page, asin="B0TEST00AA")
        assert p.price == 2570.0

    def test_rating_from_popover_title(self):
        p = parse_product(GOOD_PAGE, asin="B0TEST00AA")
        assert p.rating == 4.4

    def test_rating_from_icon_alt_fallback(self):
        page = full_page(TITLE_HTML, RATING_ALT_ONLY_HTML)
        p = parse_product(page, asin="B0TEST00AA")
        assert p.rating == 4.7

    def test_reviews_from_aria_label(self):
        p = parse_product(GOOD_PAGE, asin="B0TEST00AA")
        assert p.reviews_count == 172

    def test_reviews_from_ratings_text(self):
        page = full_page(TITLE_HTML, REVIEWS_RATINGS_TEXT_HTML)
        p = parse_product(page, asin="B0TEST00AA")
        assert p.reviews_count == 12345

    def test_availability_in_stock(self):
        p = parse_product(GOOD_PAGE, asin="B0TEST00AA")
        assert p.availability == "In Stock"
        assert p.is_in_stock is True

    def test_availability_unavailable(self):
        page = full_page(TITLE_HTML, AVAILABILITY_UNAVAILABLE_HTML)
        p = parse_product(page, asin="B0TEST00AA")
        assert p.is_in_stock is False

    def test_bsr_first_rank(self):
        p = parse_product(GOOD_PAGE, asin="B0TEST00AA")
        assert p.bsr == 217
        assert p.bsr_category == "Computers & Accessories"

    def test_missing_fields_are_none_not_crash(self):
        p = parse_product(full_page(TITLE_HTML), asin="B0TEST00AA")
        assert p.price is None
        assert p.rating is None
        assert p.reviews_count is None
        assert p.bsr is None

    def test_asin_passthrough(self):
        p = parse_product(GOOD_PAGE, asin="B0TEST00AA")
        assert p.asin == "B0TEST00AA"

    def test_to_dict_is_json_safe(self):
        import json
        p = parse_product(GOOD_PAGE, asin="B0TEST00AA")
        json.dumps(p.to_dict())  # must not raise

    def test_complete_flag(self):
        good = parse_product(GOOD_PAGE, asin="B0TEST00AA")
        assert good.is_complete() is True
        sparse = parse_product(full_page(TITLE_HTML), asin="B0TEST00AA")
        assert sparse.is_complete() is False

    def test_twister_json_prefers_new_offer_over_used(self):
        used_first = full_page(TITLE_HTML, """
<div id="twister-plus-buying-options-price-data" class="aok-hidden">
{"desktop_buybox_group_1":[{"displayPrice":"$99.00","priceAmount":99.00,"buyingOptionType":"USED"}],
 "desktop_buybox_group_2":[{"displayPrice":"$150.00","priceAmount":150.00,"buyingOptionType":"NEW"}]}
</div>
""")
        p = parse_product(used_first, asin="B0TEST00AA")
        assert p.price == 150.0

    def test_no_buybox_offer_is_definitive(self):
        page = full_page(TITLE_HTML, NO_OFFER_HTML, RATING_HTML, REVIEWS_ARIA_HTML)
        p = parse_product(page, asin="B0TEST00AA")
        assert p.price is None
        assert p.availability == "See All Buying Options"
        assert p.is_definitive() is True

    def test_missing_price_without_aod_marker_not_definitive(self):
        page = full_page(TITLE_HTML, RATING_HTML, REVIEWS_ARIA_HTML)
        p = parse_product(page, asin="B0TEST00AA")
        assert p.is_definitive() is False

    def test_rating_markup_not_used_as_price(self):
        """Regression: AirPods Max pilot wrote price=$4.60, rating=16685."""
        page = full_page(TITLE_HTML, RATING_AS_PRICE_HTML)
        p = parse_product(page, asin="B0DGJBQSJY")
        assert p.price is None
        assert p.rating == 4.6
        assert p.reviews_count == 16685

    def test_rating_never_exceeds_five(self):
        page = full_page(
            TITLE_HTML,
            """<span data-hook="rating-out-of-text">16,685 ratings</span>""",
        )
        p = parse_product(page, asin="B0TEST00AA")
        assert p.rating is None


# ── ProductData immutability (frozen dataclass per house style) ─────────────

class TestProductDataImmutable:
    def test_frozen(self):
        p = ProductData(asin="B0TEST00AA")
        with pytest.raises(Exception):
            p.price = 1.0  # type: ignore[misc]


# ── list price + "bought in past month" badge (deals signals) ────────────────

class TestDealSignals:
    def test_list_price_from_strikethrough(self):
        page = full_page(TITLE_HTML, TWISTER_JSON_HTML, LIST_PRICE_HTML)
        p = parse_product(page, asin="B0TEST00AA")
        assert p.list_price == 199.99
        # current buy-box price still comes from twister JSON, not the strike
        assert p.price == 2570.00

    def test_list_price_absent_is_none(self):
        p = parse_product(GOOD_PAGE, asin="B0TEST00AA")
        assert p.list_price is None

    def test_bought_badge_k_suffix(self):
        page = full_page(TITLE_HTML, BOUGHT_BADGE_HTML)
        p = parse_product(page, asin="B0TEST00AA")
        assert p.bought_past_month == 1000

    def test_bought_badge_plain_number(self):
        page = full_page(TITLE_HTML, '<span>400+ bought in past month</span>')
        p = parse_product(page, asin="B0TEST00AA")
        assert p.bought_past_month == 400

    def test_bought_badge_absent_is_none(self):
        p = parse_product(GOOD_PAGE, asin="B0TEST00AA")
        assert p.bought_past_month is None
