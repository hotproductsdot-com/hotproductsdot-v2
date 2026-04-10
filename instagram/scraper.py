"""
HotProducts scraper — fetches today's featured products from hotproductsdot.com.
Parses product name, rating, review count, category, image URL, price, and Amazon link.
"""
import re
import time
import urllib.request
import urllib.parse
import html
from datetime import datetime

BASE = "https://hotproductsdot.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}


def _fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_og_desc(og_desc):
    """Parse '4.2★ · 319 reviews · Home' into structured fields."""
    stars, reviews, category = None, None, ""
    m = re.match(r"([\d.]+)★\s*·\s*([\d,]+)\s*reviews?\s*·\s*(.+)", og_desc or "")
    if m:
        stars    = float(m.group(1))
        reviews  = int(m.group(2).replace(",", ""))
        category = m.group(3).strip()
    return stars, reviews, category


def get_homepage_slugs():
    """Return deduplicated product slugs listed on the homepage."""
    html = _fetch(BASE)
    raw  = re.findall(r'href=\"(/products/[^\"/?]+/)\"', html)
    seen, out = set(), []
    for path in raw:
        slug = path.strip("/").split("/")[-1]
        if slug and slug not in seen:
            seen.add(slug)
            out.append(slug)
    return out


def get_product(slug):
    """
    Fetch a single product page and return a dict with all scraped fields.
    Returns None if the page can't be parsed.
    """
    url  = f"{BASE}/products/{slug}/"
    try:
        page = _fetch(url)
    except Exception as e:
        print(f"[scraper] fetch error {url}: {e}")
        return None

    name     = (re.findall(r'og:title\" content=\"([^\"]+)\"', page) or [""])[0]
    og_desc  = (re.findall(r'og:description\" content=\"([^\"]+)\"', page) or [""])[0]
    image    = (re.findall(r'og:image\" content=\"([^\"]+)\"', page) or [""])[0]
    stars, reviews, category = _parse_og_desc(html.unescape(og_desc))

    # Price — first dollar amount that looks real (skip $1 cookie/bot traps)
    all_prices = re.findall(r'\$(\d[\d,]*\.?\d*)', page)
    price = None
    for p in all_prices:
        val = float(p.replace(",", ""))
        if val > 5:
            price = val
            break

    # Amazon affiliate link (already contains the tag)
    amz_links = re.findall(
        r'href=\"(https://www\.amazon\.com/dp/[^\"]+)\"', page
    )
    amazon_url = amz_links[0].replace("&amp;", "&") if amz_links else ""

    if not name:
        return None

    return {
        "slug":       slug,
        "name":       name,
        "stars":      stars,
        "reviews":    reviews,
        "category":   category,
        "image_url":  image,
        "price":      price,
        "amazon_url": amazon_url,
        "page_url":   url,
    }


def get_all_products(delay=0.5):
    """Scrape all products from the homepage. Returns list sorted by score."""
    slugs    = get_homepage_slugs()
    products = []
    for slug in slugs:
        p = get_product(slug)
        if p and p["stars"] and p["reviews"]:
            # Score: weighted by reviews × stars (more reviews = more signal)
            p["score"] = p["stars"] * (p["reviews"] ** 0.4)
            products.append(p)
        time.sleep(delay)

    products.sort(key=lambda x: x["score"], reverse=True)
    return products
