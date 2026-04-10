"""
Instagram Graph API poster.
Requires an Instagram Business/Creator account connected to a Facebook Page.

Credentials in hotproductsdot-v2/.env:
  IG_USER_ID      — numeric IG account ID
  IG_ACCESS_TOKEN — long-lived page access token (valid 60 days)

Graph API flow:
  1. POST /{user_id}/media       → creates image container, returns creation_id
  2. POST /{user_id}/media_publish → publishes the container
"""
import os
import json
import urllib.request
import urllib.parse

GRAPH_BASE = "https://graph.facebook.com/v21.0"


def _graph(method, path, params):
    url  = f"{GRAPH_BASE}{path}"
    data = urllib.parse.urlencode(params).encode()
    req  = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return None, f"HTTP {e.code}: {body}"
    except Exception as e:
        return None, str(e)


def post_image(image_url, caption):
    """
    Upload image_url + caption to Instagram. Returns (post_id, error).
    image_url must be publicly accessible (https).
    """
    user_id = os.environ.get("IG_USER_ID", "")
    token   = os.environ.get("IG_ACCESS_TOKEN", "")

    if not user_id or not token:
        return None, "IG_USER_ID or IG_ACCESS_TOKEN not set in hotproductsdot-v2/.env"

    # Step 1 — create media container
    result, err = _graph("POST", f"/{user_id}/media", {
        "image_url":    image_url,
        "caption":      caption,
        "access_token": token,
    })
    if err:
        return None, f"Container creation failed: {err}"

    creation_id = result.get("id")
    if not creation_id:
        return None, f"No creation_id in response: {result}"

    # Step 2 — publish
    result, err = _graph("POST", f"/{user_id}/media_publish", {
        "creation_id":  creation_id,
        "access_token": token,
    })
    if err:
        return None, f"Publish failed: {err}"

    post_id = result.get("id")
    return post_id, None


def check_credentials():
    """Verify credentials are present and token is valid."""
    user_id = os.environ.get("IG_USER_ID", "")
    token   = os.environ.get("IG_ACCESS_TOKEN", "")
    if not user_id or not token:
        return False, "Credentials missing"

    result, err = _graph("GET", f"/{user_id}", {"fields": "username,name", "access_token": token})
    if err:
        return False, err
    return True, result.get("username", "unknown")
