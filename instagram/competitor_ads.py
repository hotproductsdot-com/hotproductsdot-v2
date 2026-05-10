"""ScrapeCreators competitor ad fetcher.

Pulls live ads from the Facebook (Meta) Ad Library by keyword/brand and
returns normalized image URLs the AI ad-creative pipeline can ground on,
in place of (or alongside) Tavily generic web references.

Adapted from Samin Yasar's "Claude Just Changed Marketing Forever" tutorial
(2026-04-27), Level 3 — competitor ad analysis.

Endpoint: GET https://api.scrapecreators.com/v1/facebook/adLibrary/search/ads
Auth: x-api-key header
Docs: https://docs.scrapecreators.com/v1/facebook/adLibrary/search/ads

The module fails soft: any error returns an empty list so the upstream
ad-creative pipeline can fall back to Tavily and ultimately to the
white-card banner. Never raises into the daily rotation.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

ENDPOINT = "https://api.scrapecreators.com/v1/facebook/adLibrary/search/ads"
DEFAULT_TIMEOUT = 15
DEFAULT_COUNTRY = "US"
DEFAULT_MEDIA_TYPE = "IMAGE"  # exclude video for static-banner grounding
DEFAULT_SORT_BY = "total_impressions"  # highest-performing first
DEFAULT_LIMIT = 5


@dataclass(frozen=True)
class CompetitorAd:
    """One normalized ad row used by ad_creative_gen."""

    archive_id: str
    page_name: str
    image_urls: tuple[str, ...]
    title: str
    body: str
    cta_text: str
    is_active: bool


def _get_api_key() -> str | None:
    return os.environ.get("SCRAPECREATORS_API_KEY")


def _normalize(raw: dict) -> CompetitorAd | None:
    """Lift the fields we care about out of the SC response shape.

    SC nests the creative under `snapshot`; images is a list whose entries
    expose `original_image_url` and `resized_image_url` (the resized one is
    cheaper to fetch and large enough for Gemini grounding).
    """
    snap = raw.get("snapshot") or {}
    images = snap.get("images") or []
    urls: list[str] = []
    for img in images:
        url = img.get("resized_image_url") or img.get("original_image_url")
        if url:
            urls.append(url)
    if not urls:
        return None
    body = ((snap.get("body") or {}).get("text")) or ""
    return CompetitorAd(
        archive_id=str(raw.get("ad_archive_id") or ""),
        page_name=str(raw.get("page_name") or snap.get("current_page_name") or ""),
        image_urls=tuple(urls),
        title=str(snap.get("title") or ""),
        body=str(body),
        cta_text=str(snap.get("cta_text") or ""),
        is_active=bool(raw.get("is_active", False)),
    )


def fetch_competitor_ads(
    query: str,
    *,
    limit: int = DEFAULT_LIMIT,
    country: str = DEFAULT_COUNTRY,
    media_type: str = DEFAULT_MEDIA_TYPE,
    sort_by: str = DEFAULT_SORT_BY,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[CompetitorAd]:
    """Search the Facebook Ad Library for active ads matching `query`.

    Returns up to `limit` normalized rows ordered by impressions. Empty list
    on missing API key, HTTP error, parse error, or zero results — never
    raises.
    """
    api_key = _get_api_key()
    if not api_key:
        logger.info("SCRAPECREATORS_API_KEY unset; skipping competitor ad fetch")
        return []
    if not query or not query.strip():
        return []

    params = {
        "query": query.strip(),
        "country": country,
        "media_type": media_type,
        "status": "ACTIVE",
        "sort_by": sort_by,
    }
    headers = {"x-api-key": api_key}

    try:
        resp = requests.get(ENDPOINT, params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("ScrapeCreators fetch failed: %s", exc)
        return []

    results = payload.get("searchResults") or []
    out: list[CompetitorAd] = []
    for row in results:
        if len(out) >= limit:
            break
        norm = _normalize(row)
        if norm is None:
            continue
        out.append(norm)
    logger.info(
        "ScrapeCreators: query=%r → %d ads (asked %d)", query, len(out), limit
    )
    return out


def collect_reference_image_urls(query: str, n: int) -> list[str]:
    """Convenience: flatten competitor ads into a flat URL list, capped at n.

    This is the integration point the ad-creative pipeline calls when the
    user passes --competitor-brand. Falls back to empty list on failure so
    the caller can route to Tavily.
    """
    if n <= 0:
        return []
    ads = fetch_competitor_ads(query, limit=max(n, DEFAULT_LIMIT))
    urls: list[str] = []
    for ad in ads:
        for u in ad.image_urls:
            urls.append(u)
            if len(urls) >= n:
                return urls
    return urls
