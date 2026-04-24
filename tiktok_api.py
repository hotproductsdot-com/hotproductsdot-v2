"""
TikTok Content Posting + OAuth v2 client.

Environment variables:
    TIKTOK_ACCESS_TOKEN   — short-lived access token (24 h) with video.publish scope.
                            Refresh with `python -m tiktok_api refresh`.
    TIKTOK_REFRESH_TOKEN  — long-lived refresh token (365 d) from the initial OAuth flow.
    TIKTOK_CLIENT_KEY     — app client key from https://developers.tiktok.com/
    TIKTOK_CLIENT_SECRET  — app client secret

Docs:
    https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
    https://developers.tiktok.com/doc/oauth-user-access-token-management

Note: The content-posting API uses `video.publish` scope even for photo posts — that
naming is a TikTok quirk, not a bug.
"""

import argparse
import json
import os
import subprocess
import sys

import requests

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"
OAUTH_TOKEN_URL = f"{TIKTOK_API_BASE}/oauth/token/"


# ─── Content posting ─────────────────────────────────────────────────────────


def post_photo(
    image_urls: list[str],
    caption: str,
    cover_index: int = 0,
    auto_add_music: bool = True,
    *,
    access_token: str | None = None,
) -> dict:
    """
    Publish a photo post directly to TikTok.

    Args:
        image_urls:      One or more publicly accessible image URLs. The host domain
                         must be verified in the TikTok Developer portal under
                         "URL prefix properties".
        caption:         Post title/caption (max 2,200 chars).
        cover_index:     Which image to use as the cover (default: 0).
        auto_add_music:  Let TikTok auto-add background music.
        access_token:    Overrides TIKTOK_ACCESS_TOKEN env var (useful right after refresh).

    Returns:
        dict with keys: ok (bool), publish_id (str on success), error (str on failure)
    """
    token = access_token or os.environ.get("TIKTOK_ACCESS_TOKEN", "")
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

    # Content-posting errors are nested: {"error": {"code": "...", "message": "..."}}
    err = data.get("error", {})
    if resp.status_code != 200 or err.get("code") != "ok":
        return {"ok": False, "error": err.get("message") or str(data)}

    return {"ok": True, "publish_id": data.get("data", {}).get("publish_id", "")}


def fetch_trends() -> list[str]:
    """Return trending hashtags via TikTok Research API (requires separate scope)."""
    # Placeholder — TikTok Research API requires academic/business approval.
    return []


# ─── OAuth token management ──────────────────────────────────────────────────


def _oauth_post(form: dict, timeout: int) -> dict:
    """
    POST to /v2/oauth/token/ and normalise the response shape.

    OAuth errors are FLAT: {"error": "invalid_grant", "error_description": "..."}
    This differs from the content-posting API, which nests errors under "error.code".
    """
    try:
        resp = requests.post(
            OAUTH_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=form,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return {"ok": False, "error": f"HTTP request failed: {exc}"}

    try:
        data = resp.json()
    except ValueError:
        return {"ok": False, "error": f"Non-JSON response (HTTP {resp.status_code}): {resp.text[:300]}"}

    if isinstance(data.get("error"), str):
        desc = data.get("error_description") or data["error"]
        return {"ok": False, "error": f"{data['error']}: {desc}"}

    if resp.status_code != 200 or "access_token" not in data:
        return {"ok": False, "error": f"HTTP {resp.status_code}: {json.dumps(data)[:300]}"}

    return {
        "ok": True,
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "expires_in": data.get("expires_in", 0),
        "refresh_expires_in": data.get("refresh_expires_in", 0),
        "scope": data.get("scope", ""),
        "open_id": data.get("open_id", ""),
    }


def refresh_access_token(
    *,
    client_key: str | None = None,
    client_secret: str | None = None,
    refresh_token: str | None = None,
    timeout: int = 15,
) -> dict:
    """
    Exchange a TikTok refresh_token for a fresh access_token.

    A NEW refresh_token is also returned — it must be persisted. The previous
    refresh_token is invalidated after a short grace period.

    Args default to env: TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REFRESH_TOKEN.

    Returns dict with: ok, access_token, refresh_token, expires_in,
    refresh_expires_in, scope, open_id, error.
    """
    ck = client_key or os.environ.get("TIKTOK_CLIENT_KEY", "")
    cs = client_secret or os.environ.get("TIKTOK_CLIENT_SECRET", "")
    rt = refresh_token or os.environ.get("TIKTOK_REFRESH_TOKEN", "")

    missing = [
        name for name, val in (
            ("TIKTOK_CLIENT_KEY", ck),
            ("TIKTOK_CLIENT_SECRET", cs),
            ("TIKTOK_REFRESH_TOKEN", rt),
        ) if not val
    ]
    if missing:
        return {"ok": False, "error": f"Missing env var(s): {', '.join(missing)}"}

    # Fall back to refresh_token echo on rotation-disabled apps.
    result = _oauth_post(
        {
            "client_key": ck,
            "client_secret": cs,
            "grant_type": "refresh_token",
            "refresh_token": rt,
        },
        timeout,
    )
    if result["ok"] and not result["refresh_token"]:
        result["refresh_token"] = rt
    return result


def exchange_authorization_code(
    code: str,
    redirect_uri: str,
    *,
    client_key: str | None = None,
    client_secret: str | None = None,
    timeout: int = 15,
) -> dict:
    """
    One-time bootstrap: exchange an authorization `code` for initial access + refresh tokens.

    Walk the user through the authorize URL first (RUNBOOK § TikTok token refresh),
    capture the `code` from the redirect, then run this.
    """
    ck = client_key or os.environ.get("TIKTOK_CLIENT_KEY", "")
    cs = client_secret or os.environ.get("TIKTOK_CLIENT_SECRET", "")

    missing = [
        name for name, val in (
            ("TIKTOK_CLIENT_KEY", ck),
            ("TIKTOK_CLIENT_SECRET", cs),
        ) if not val
    ]
    if missing:
        return {"ok": False, "error": f"Missing env var(s): {', '.join(missing)}"}

    return _oauth_post(
        {
            "client_key": ck,
            "client_secret": cs,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout,
    )


# ─── CLI: python -m tiktok_api {refresh,exchange-code} ───────────────────────


def _update_github_secrets(access_token: str, refresh_token: str) -> int:
    """
    Persist new tokens to GitHub Actions secrets via `gh secret set`.

    Requires:
        GH_REPO env var (OWNER/REPO)
        GH_TOKEN env var containing a fine-grained PAT with "Secrets: Read and write"
        on the target repo. The default GITHUB_TOKEN does NOT grant secrets:write.
    """
    repo = os.environ.get("GH_REPO", "")
    if not repo:
        print("✗ GH_REPO env not set (expected OWNER/REPO)", file=sys.stderr)
        return 1
    if not os.environ.get("GH_TOKEN") and not os.environ.get("GITHUB_TOKEN"):
        print(
            "✗ GH_TOKEN (or GITHUB_TOKEN) not set. Needs a fine-grained PAT "
            "with 'Secrets: Read and write' — the default GITHUB_TOKEN cannot write secrets.",
            file=sys.stderr,
        )
        return 1

    for name, value in (
        ("TIKTOK_ACCESS_TOKEN", access_token),
        ("TIKTOK_REFRESH_TOKEN", refresh_token),
    ):
        try:
            subprocess.run(
                ["gh", "secret", "set", name, "--repo", repo, "--body", value],
                check=True,
                capture_output=True,
                text=True,
            )
            print(f"✓ Updated secret: {name}")
        except FileNotFoundError:
            print("✗ `gh` CLI not found on PATH", file=sys.stderr)
            return 1
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            print(f"✗ Failed to update {name}: {stderr}", file=sys.stderr)
            return 1
    return 0


def _print_tokens(result: dict) -> None:
    print(
        f"✓ Refreshed. access_token expires in {result['expires_in']}s "
        f"({result['expires_in'] // 3600} h), refresh_token expires in "
        f"{result['refresh_expires_in']}s ({result['refresh_expires_in'] // 86400} d)."
    )
    print(f"  scope         : {result.get('scope', '')}")
    print(f"  open_id       : {result.get('open_id', '')}")
    print(f"  access_token  : {result['access_token']}")
    print(f"  refresh_token : {result['refresh_token']}  ← persist this!")


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tiktok_api", description="TikTok API utilities")
    sub = parser.add_subparsers(dest="cmd", required=True)

    refresh_p = sub.add_parser("refresh", help="Refresh the TikTok access token")
    refresh_p.add_argument("--json", action="store_true", help="Machine-readable JSON on stdout")
    refresh_p.add_argument(
        "--github",
        action="store_true",
        help="Also update TIKTOK_ACCESS_TOKEN + TIKTOK_REFRESH_TOKEN repo secrets via `gh` "
        "CLI. Requires GH_REPO env (OWNER/REPO) and GH_TOKEN env with a fine-grained PAT "
        "that has 'Secrets: Read and write' on this repo. The default GITHUB_TOKEN will NOT work.",
    )

    exch_p = sub.add_parser(
        "exchange-code",
        help="One-time bootstrap: exchange an authorization `code` for initial tokens",
    )
    exch_p.add_argument("--code", required=True, help="The `code` query param from the OAuth redirect")
    exch_p.add_argument("--redirect-uri", required=True, help="The exact redirect_uri used in the authorize URL")
    exch_p.add_argument("--json", action="store_true", help="Machine-readable JSON on stdout")

    args = parser.parse_args(argv)

    if args.cmd == "refresh":
        result = refresh_access_token()
    else:  # exchange-code
        result = exchange_authorization_code(code=args.code, redirect_uri=args.redirect_uri)

    if args.json:
        print(json.dumps(result))
    elif result["ok"]:
        _print_tokens(result)
    else:
        print(f"✗ {result['error']}", file=sys.stderr)

    if not result["ok"]:
        return 1

    if args.cmd == "refresh" and getattr(args, "github", False):
        return _update_github_secrets(result["access_token"], result["refresh_token"])
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
