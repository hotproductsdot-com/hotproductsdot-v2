#!/usr/bin/env python3
"""amazon_local_api.py — local, free equivalent of Oxylabs "amazon_product".

Given an ASIN, returns structured product data (title, price, rating,
review count, availability, Best Sellers Rank) scraped directly from
amazon.com — no paid API.

Reliability model (the "100% success" contract):
  * Engine ladder: curl_cffi Chrome TLS impersonation → curl_cffi Safari →
    Scrapling FetcherSession. Blocked/garbage responses rotate to the next
    engine with jittered backoff instead of failing.
  * Field parsing uses layered strategies (embedded buy-box JSON first,
    then scoped DOM selectors, then assembled price parts) so markup
    variants still parse.
  * Every ASIN ends in a definitive verdict: parsed data, "not_found"
    (listing removed), or "unavailable" — never a silent failure.

Library use:
    from amazon_local_api import fetch_product
    product = fetch_product("B0DW1X5YCQ")     # -> ProductData

CLI use:
    venv/bin/python amazon_local_api.py B0DW1X5YCQ B0GR6BVYS5 --pretty
"""
from __future__ import annotations

import argparse
import dataclasses
import html as html_lib
import json
import random
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from bs4 import BeautifulSoup

AMAZON_URL = "https://www.amazon.com/dp/{asin}"
# Alternate URL forms rotated across retry attempts — Amazon's bot checks
# are URL-form-specific (verified: /dp/ CAPTCHA'd while /gp/product/ passed).
URL_FORMS = [
    "https://www.amazon.com/dp/{asin}",
    "https://www.amazon.com/gp/product/{asin}",
]
DEFAULT_HEADERS = {"Accept-Language": "en-US,en;q=0.9"}

# Ordered: most reliable / least detectable first. firefox impersonation is
# deliberately absent — it gets blocked by Amazon (verified 2026-06-10).
ENGINE_ORDER = ["curl_chrome", "curl_safari", "scrapling"]

_BLOCK_RE = re.compile(
    r"(Robot Check|Type the characters you see|validateCaptcha|"
    r"api-services-support@amazon\.com)",
    re.IGNORECASE,
)
_DOG_RE = re.compile(r"(dogsofamazon|Sorry! Something went wrong)", re.IGNORECASE)
_UNAVAILABLE_RE = re.compile(
    r"(currently\s+unavailable|out\s+of\s+stock|sold\s+out|"
    r"cannot\s+be\s+shipped|\bunavailable\b)",
    re.IGNORECASE,
)
_RATING_RE = re.compile(r"(\d(?:\.\d)?)\s+out\s+of\s+5")
_REVIEWS_RE = re.compile(r"([\d,]+)\s*(?:Reviews?|ratings?)", re.IGNORECASE)
_BSR_RE = re.compile(r"#([\d,]+)\s+in\s+([^(#]+?)(?:\s*\(|\s*$|\s{2,})")
_TWISTER_PRICE_ID = "twister-plus-buying-options-price-data"

# Containers whose prices belong to OTHER products (comparison widgets,
# carousels, customer-review headers) — never use these for the buy-box price.
_TRAP_CONTAINER_RE = re.compile(
    r"(comparison|carousel|sims|sponsored|averageCustomerReviews|acrPopover|"
    r"reviewsMedley|customerReviews|CustomerReviews|cm_cr_dp_d_rating)",
    re.IGNORECASE,
)
# Price-like text that is actually a star rating or review count.
_PRICE_TEXT_REJECT_RE = re.compile(
    r"(out\s+of\s+5|\bstars?\b|\bratings?\b|\breviews?\b)",
    re.IGNORECASE,
)
_BARE_COUNT_RE = re.compile(r"^[\(\s]*[\d,]+[\)\s]*$")


@dataclass(frozen=True)
class ProductData:
    """Structured scrape result for one ASIN. Mirrors the useful subset of
    the Oxylabs amazon_product schema."""
    asin: str
    title: str | None = None
    price: float | None = None
    currency: str | None = None
    rating: float | None = None
    reviews_count: int | None = None
    availability: str | None = None
    is_in_stock: bool | None = None
    bsr: int | None = None
    bsr_category: str | None = None
    url: str = ""
    page_status: str = "ok"          # ok | blocked | not_found | server_error | suspect | error
    engine: str | None = None
    attempts: int = 0
    fetched_at: str = ""
    error: str | None = None
    signals: dict = field(default_factory=dict)

    def is_complete(self) -> bool:
        """True when the fields the catalog needs were all extracted."""
        return None not in (self.title, self.price, self.rating, self.reviews_count)

    def is_definitive(self) -> bool:
        """True when this result is a final answer for the ASIN: either the
        data parsed, or the listing is definitively gone/unavailable."""
        if self.page_status == "not_found":
            return True
        if self.page_status == "ok" and self.is_in_stock is False and self.title:
            return True  # unavailable listings legitimately have no price
        if (self.page_status == "ok" and self.title
                and self.availability == "See All Buying Options"):
            return True  # no-buy-box listing: price genuinely absent
        return self.page_status == "ok" and self.is_complete()

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


# ── Parsing helpers ──────────────────────────────────────────────────────────

def parse_price_string(
    s: str | None,
    *,
    require_currency: bool = False,
) -> float | None:
    """'$2,570.00' → 2570.0; '$19.99 - $29.99' → 19.99; junk → None."""
    if not s:
        return None
    text = s.strip()
    if _PRICE_TEXT_REJECT_RE.search(text):
        return None
    if _BARE_COUNT_RE.match(text):
        return None
    if require_currency and "$" not in text and "USD" not in text.upper():
        return None
    low_end = text.split("-")[0]
    cleaned = re.sub(r"[^\d.]", "", low_end.replace(",", ""))
    if not cleaned or cleaned == ".":
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value > 0 else None


def classify_page(body: str, status_code: int) -> str:
    """Classify a fetched page so the engine ladder knows whether to retry."""
    if status_code == 404:
        return "not_found"
    if status_code >= 500 or _DOG_RE.search(body[:200000]):
        return "server_error"
    if _BLOCK_RE.search(body[:200000]):
        return "blocked"
    if status_code != 200:
        return "error"
    if 'id="productTitle"' not in body:
        return "suspect"  # 200 but not a product page — soft block or redirect
    return "ok"


def _in_trap_container(el) -> bool:
    for parent in el.parents:
        attrs = " ".join(
            [str(parent.get("id") or "")] + list(parent.get("class") or [])
        )
        if attrs and _TRAP_CONTAINER_RE.search(attrs):
            return True
    return False


def _container_has_currency_symbol(container) -> bool:
    symbol = container.select_one(".a-price-symbol")
    return bool(symbol and "$" in symbol.get_text())


def _coerce_rating(value: float | None) -> float | None:
    if value is None or not (0.0 < value <= 5.0):
        return None
    return value


def _reject_price_rating_collision(
    price: float | None,
    rating: float | None,
    *,
    twister_confirmed: bool,
) -> float | None:
    """Drop DOM prices that are really the star rating (2026-06-10 catalog bug)."""
    if price is None or rating is None or twister_confirmed:
        return price
    if price <= 5.0 and abs(price - rating) < 0.15:
        return None
    return price


def _price_from_twister_json(body: str) -> float | None:
    """Most reliable source: the embedded buy-box JSON blob."""
    marker = body.find(_TWISTER_PRICE_ID)
    if marker == -1:
        return None
    window = body[marker:marker + 20000]
    start = window.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(window[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(html_lib.unescape(window[start:i + 1]))
                except (ValueError, TypeError):
                    return None
                fallback: float | None = None
                for group in data.values():
                    if not (isinstance(group, list) and group):
                        continue
                    amount = group[0].get("priceAmount")
                    if not (isinstance(amount, (int, float)) and amount > 0):
                        continue
                    # Prefer the NEW-condition offer; a used/renewed offer can
                    # appear first when the new buy box is empty.
                    if group[0].get("buyingOptionType", "NEW") == "NEW":
                        return float(amount)
                    if fallback is None:
                        fallback = float(amount)
                return fallback
    return None


_SCOPED_PRICE_SELECTORS = [
    ".apex-pricetopay-value .a-offscreen",
    "#apex_offerDisplay_desktop .a-offscreen",
    "#corePrice_feature_div .a-offscreen",
    "#buybox .a-price .a-offscreen",
    "#priceblock_ourprice",
    "#price",
]

_PRICE_PARTS_CONTAINERS = [
    ".apex-pricetopay-value",
    ".priceToPay",
    "#corePrice_feature_div .a-price",
    "#apex_offerDisplay_desktop .a-price",
]


def _price_from_selectors(soup: BeautifulSoup) -> float | None:
    for sel in _SCOPED_PRICE_SELECTORS:
        for el in soup.select(sel):
            if _in_trap_container(el):
                continue
            value = parse_price_string(el.get_text(strip=True))
            if value is not None:
                return value
    return None


def _price_from_parts(soup: BeautifulSoup) -> float | None:
    """Assemble price from a-price-whole + a-price-fraction (the offscreen
    span is empty on many current Amazon pages)."""
    for sel in _PRICE_PARTS_CONTAINERS:
        for container in soup.select(sel):
            if _in_trap_container(container):
                continue
            if not _container_has_currency_symbol(container):
                continue
            whole = container.select_one(".a-price-whole")
            if not whole:
                continue
            whole_txt = re.sub(r"[^\d]", "", whole.get_text())
            if not whole_txt:
                continue
            frac = container.select_one(".a-price-fraction")
            frac_txt = re.sub(r"[^\d]", "", frac.get_text()) if frac else "00"
            return parse_price_string(f"{whole_txt}.{frac_txt or '00'}")
    return None


def _price_broad_fallback(soup: BeautifulSoup) -> float | None:
    for el in soup.select(".a-price .a-offscreen"):
        if _in_trap_container(el):
            continue
        value = parse_price_string(el.get_text(strip=True), require_currency=True)
        if value is not None:
            return value
    return None


def _extract_price(body: str, soup: BeautifulSoup) -> tuple[float | None, bool]:
    """Return (price, twister_confirmed)."""
    twister = _price_from_twister_json(body)
    if twister is not None:
        return twister, True
    for strategy in (
        _price_from_selectors,
        _price_from_parts,
        _price_broad_fallback,
    ):
        value = strategy(soup)
        if value is not None:
            return value, False
    return None, False


def _extract_rating(soup: BeautifulSoup) -> float | None:
    popover = soup.select_one("#acrPopover")
    if popover and popover.get("title"):
        m = _RATING_RE.search(popover["title"])
        if m:
            return _coerce_rating(float(m.group(1)))
    for el in soup.select("i.a-icon-star .a-icon-alt, span[data-hook='rating-out-of-text']"):
        m = _RATING_RE.search(el.get_text())
        if m:
            return _coerce_rating(float(m.group(1)))
    return None


def _extract_reviews(soup: BeautifulSoup) -> int | None:
    el = soup.select_one("#acrCustomerReviewText")
    if el is None:
        return None
    for text in (el.get("aria-label") or "", el.get_text(" ", strip=True)):
        m = _REVIEWS_RE.search(text)
        if m:
            return int(m.group(1).replace(",", ""))
        digits = re.search(r"\(?([\d,]+)\)?", text)
        if digits:
            return int(digits.group(1).replace(",", ""))
    return None


def _extract_availability(soup: BeautifulSoup) -> tuple[str | None, bool | None]:
    box = soup.select_one("#availability")
    if box is None:
        return None, None
    # No-buy-box listings render only the All Offers Display spinner here —
    # price genuinely isn't on the page ("See All Buying Options" state).
    if box.select_one("#all-offers-display") is not None:
        return "See All Buying Options", None
    text = " ".join(box.get_text(" ", strip=True).split())
    if not text:
        return None, None
    if _UNAVAILABLE_RE.search(text):
        return text, False
    return text, True


def _extract_bsr(body: str) -> tuple[int | None, str | None]:
    """Scan the raw HTML window after the 'Best Sellers Rank' label.
    Tag-position based (not DOM) because Amazon renders this section as a
    table row, list item, or detail bullet depending on the page template."""
    marker = body.find("Best Sellers Rank")
    if marker == -1:
        return None, None
    window = body[marker:marker + 4000]
    text = html_lib.unescape(re.sub(r"<[^>]+>", " ", window))
    text = " ".join(text.split())
    m = _BSR_RE.search(text)
    if not m:
        return None, None
    rank = int(m.group(1).replace(",", ""))
    category = m.group(2).strip()
    return rank, category


def parse_product(body: str, asin: str) -> ProductData:
    """Parse a full Amazon product page into ProductData. Network-free."""
    try:
        soup = BeautifulSoup(body, "lxml")
    except Exception:
        soup = BeautifulSoup(body, "html.parser")
    title_el = soup.select_one("#productTitle")
    title = title_el.get_text(strip=True) if title_el else None
    price, twister_confirmed = _extract_price(body, soup)
    availability, in_stock = _extract_availability(soup)
    rating = _extract_rating(soup)
    reviews = _extract_reviews(soup)
    price = _reject_price_rating_collision(price, rating, twister_confirmed=twister_confirmed)
    bsr, bsr_category = _extract_bsr(body)
    return ProductData(
        asin=asin,
        title=title,
        price=price,
        currency="USD" if price is not None else None,
        rating=rating,
        reviews_count=reviews,
        availability=availability,
        is_in_stock=in_stock,
        bsr=bsr,
        bsr_category=bsr_category,
        url=AMAZON_URL.format(asin=asin),
        fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


# ── Fetch engines ────────────────────────────────────────────────────────────

# Global pacing across ALL worker threads. Per-worker delays still allow 4
# workers to fire near-simultaneously; this floor caps the aggregate request
# rate from this IP, which is what Amazon's anti-bot actually sees.
MIN_REQUEST_INTERVAL = 1.5  # seconds between any two requests, process-wide

_throttle_lock = threading.Lock()
_last_request_at = 0.0

_thread_local = threading.local()


def _global_throttle() -> None:
    global _last_request_at
    with _throttle_lock:
        now = time.monotonic()
        wait = _last_request_at + MIN_REQUEST_INTERVAL - now
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()


def _curl_session(impersonate: str):
    """Per-thread persistent session. Cookie continuity across requests makes
    traffic look like a browsing session instead of stateless bot hits —
    cookie-less fetches are what triggered the 2026-06-11 CAPTCHA wave."""
    sessions = getattr(_thread_local, "curl_sessions", None)
    if sessions is None:
        sessions = _thread_local.curl_sessions = {}
    session = sessions.get(impersonate)
    if session is None:
        from curl_cffi import requests as creq
        session = sessions[impersonate] = creq.Session(impersonate=impersonate)
    return session


def reset_sessions() -> None:
    """Drop this thread's sessions (fresh cookies) — call after repeated blocks."""
    getattr(_thread_local, "curl_sessions", {}).clear()


def _fetch_curl(url: str, impersonate: str, timeout: int) -> tuple[str, int]:
    resp = _curl_session(impersonate).get(url, timeout=timeout, headers=DEFAULT_HEADERS)
    return resp.text, resp.status_code


def _fetch_scrapling(url: str, timeout: int) -> tuple[str, int]:
    from scrapling.fetchers import FetcherSession
    # FetcherSession is a context manager in scrapling 0.4.x — calling
    # .get() on the unentered object raises AttributeError.
    with FetcherSession() as session:
        resp = session.get(url, timeout=timeout, retries=1)
    body = resp.body.decode(resp.encoding or "utf-8", errors="replace")
    return body, resp.status


def _run_engine(name: str, url: str, timeout: int) -> tuple[str, int]:
    if name == "curl_chrome":
        return _fetch_curl(url, "chrome131", timeout)
    if name == "curl_safari":
        return _fetch_curl(url, "safari184", timeout)
    if name == "scrapling":
        return _fetch_scrapling(url, timeout)
    raise ValueError(f"unknown engine: {name}")


def _backoff(base_delay: float, attempt: int, *, blocked: bool = False) -> float:
    """Jittered backoff. Transport errors retry quickly (linear, 8s cap);
    blocked/suspect verdicts cool down exponentially (45s cap) — rapid-fire
    retries against a CAPTCHA make Amazon block the URL harder."""
    if blocked:
        return min(random.uniform(base_delay, base_delay * 2) * (2 ** (attempt - 1)), 45.0)
    return min(random.uniform(base_delay, base_delay * 2) * attempt, 8.0)


def fetch_product(
    asin: str,
    *,
    max_attempts: int = 6,
    timeout: int = 30,
    base_delay: float = 1.5,
) -> ProductData:
    """Fetch + parse one ASIN, rotating engines until a definitive result.

    Never raises. Worst case returns a ProductData whose page_status/error
    describe the last failure after max_attempts.
    """
    last: ProductData = ProductData(asin=asin, page_status="error", error="not attempted")
    for attempt in range(1, max_attempts + 1):
        engine = ENGINE_ORDER[(attempt - 1) % len(ENGINE_ORDER)]
        url = URL_FORMS[(attempt - 1) // len(ENGINE_ORDER) % len(URL_FORMS)].format(asin=asin)
        try:
            _global_throttle()
            body, status = _run_engine(engine, url, timeout)
        except Exception as exc:
            last = dataclasses.replace(
                ProductData(asin=asin, url=AMAZON_URL.format(asin=asin)),
                page_status="error", error=f"{engine}: {str(exc)[:120]}",
                engine=engine, attempts=attempt,
            )
            time.sleep(_backoff(base_delay, attempt))
            continue

        verdict = classify_page(body, status)
        if verdict == "not_found":
            return dataclasses.replace(
                parse_product(body, asin),
                page_status="not_found", engine=engine, attempts=attempt,
            )
        if verdict == "ok":
            product = dataclasses.replace(
                parse_product(body, asin), engine=engine, attempts=attempt,
            )
            if product.is_definitive():
                return product
            last = product  # parsed but incomplete — try another engine
        else:
            last = dataclasses.replace(
                ProductData(asin=asin, url=AMAZON_URL.format(asin=asin)),
                page_status=verdict, engine=engine, attempts=attempt,
                error=f"{engine}: {verdict} (HTTP {status})",
            )
            if verdict in ("blocked", "suspect"):
                reset_sessions()  # poisoned cookies — start a fresh session
                time.sleep(_backoff(base_delay, attempt, blocked=True))
                continue
        time.sleep(_backoff(base_delay, attempt))
    return last


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("asins", nargs="+", help="One or more Amazon ASINs")
    parser.add_argument("--pretty", action="store_true", help="Indented JSON output")
    parser.add_argument("--max-attempts", type=int, default=6)
    parser.add_argument("--delay", type=float, default=1.5,
                        help="Base inter-attempt delay in seconds (default 1.5)")
    args = parser.parse_args(argv)

    results = []
    for i, asin in enumerate(args.asins):
        if i:
            time.sleep(random.uniform(args.delay * 0.8, args.delay * 1.4))
        product = fetch_product(asin.strip().upper(),
                                max_attempts=args.max_attempts,
                                base_delay=args.delay)
        results.append(product.to_dict())

    payload = {"results": results}
    print(json.dumps(payload, indent=2 if args.pretty else None, ensure_ascii=False))
    failed = [r for r in results if r["page_status"] not in ("ok", "not_found")]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
