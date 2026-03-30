"""
TikTok Content Posting API v2 client.

Requires env var:
    TIKTOK_ACCESS_TOKEN — from TikTok for Developers app with
                          video.publish scope approved.

Docs: https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
"""

import os
import requests

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"


def post_photo(
    image_urls: list[str],
    caption: str,
    cover_index: int = 0,
    auto_add_music: bool = True,
) -> dict:
    """
    Publish a photo post directly to TikTok.

    Args:
        image_urls:      One or more publicly accessible image URLs.
        caption:         Post title/caption (max 2,200 chars).
        cover_index:     Which image to use as the cover (default: 0).
        auto_add_music:  Let TikTok auto-add background music.

    Returns:
        dict with keys: ok (bool), publish_id (str on success), error (str on failure)
    """
    token = os.environ.get("TIKTOK_ACCESS_TOKEN", "")
    if not token:
        return {"ok": False, "error": "TIKTOK_ACCESS_TOKEN not set"}

    payload = {
        "post_info": {
            "title": caption[:2200],
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_comment": False,
            "auto_add_music": auto_add_music,
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "photo_images": image_urls,
            "photo_cover_index": cover_index,
        },
        "media_type": "PHOTO",
        "post_mode": "DIRECT_POST",
    }

    try:
        resp = requests.post(
            f"{TIKTOK_API_BASE}/post/publish/content/init/",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json=payload,
            timeout=30,
        )
        data = resp.json()
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc)}

    err = data.get("error", {})
    if resp.status_code != 200 or err.get("code") != "ok":
        return {"ok": False, "error": err.get("message") or str(data)}

    return {"ok": True, "publish_id": data.get("data", {}).get("publish_id", "")}


def fetch_trends() -> list[str]:
    """Return trending hashtags via TikTok Research API (requires separate scope)."""
    # Placeholder — TikTok Research API requires academic/business approval.
    return []
