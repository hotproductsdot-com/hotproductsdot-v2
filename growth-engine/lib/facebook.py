"""Facebook Graph API — post a link to a Facebook Page feed."""
from __future__ import annotations

import os
from typing import Any, Dict

import requests

from .config import is_dry_run


def _page_id() -> str:
    v = os.environ.get("FB_PAGE_ID", "").strip()
    if not v:
        raise RuntimeError("FB_PAGE_ID not set in environment")
    return v


def _access_token() -> str:
    v = os.environ.get("FB_PAGE_ACCESS_TOKEN", "").strip()
    if not v:
        raise RuntimeError("FB_PAGE_ACCESS_TOKEN not set in environment")
    return v


def post_link(*, message: str, link: str) -> Dict[str, Any]:
    """Post a link + message to the Facebook Page feed.

    Returns the Graph API response dict (contains 'id' on success).
    Raises RuntimeError on API error.
    """
    if is_dry_run():
        print(f"[DRY RUN] facebook.post_link: {message[:80]}… → {link}")
        return {"id": "dry-run"}

    resp = requests.post(
        f"https://graph.facebook.com/v19.0/{_page_id()}/feed",
        data={"message": message, "link": link, "access_token": _access_token()},
        timeout=20,
    )
    if not resp.ok:
        raise RuntimeError(f"Facebook API error {resp.status_code}: {resp.text[:200]}")
    return resp.json()
