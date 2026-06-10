#!/usr/bin/env python3
"""List saved FAL workflows for the authenticated user."""
from __future__ import annotations

import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

API_URL = "https://api.fal.ai/v1/workflows"


def _fetch_workflows(key: str, *, search: str | None = None) -> list[dict]:
    params: dict[str, str | int] = {"limit": 50}
    if search:
        params["search"] = search
    resp = requests.get(
        API_URL,
        headers={"Authorization": f"Key {key}"},
        params=params,
        timeout=30,
    )
    if not resp.ok:
        print(f"API error {resp.status_code}: {resp.text[:500]}", file=sys.stderr)
        sys.exit(1)
    return resp.json().get("workflows") or []


def _print_workflows(workflows: list[dict]) -> None:
    print("Saved workflows (use with --mode saved --workflow-endpoint ...):")
    for wf in workflows:
        name = wf.get("name", "")
        title = wf.get("title", "")
        user = wf.get("user_nickname", "")
        endpoint = f"workflows/{user}/{name}" if user and name else ""
        print(f"  {endpoint}")
        if title:
            print(f"    title: {title}")

    first = workflows[0]
    user = first.get("user_nickname", "")
    name = first.get("name", "")
    print("\nExample (copy after list_workflows shows your real endpoint):")
    print(
        f"  python instagram/fal-workflow/run_batch.py --mode saved "
        f'--workflow-endpoint "workflows/{user}/{name}" --slug vitamix-7500'
    )


def main() -> None:
    key = os.environ.get("FAL_KEY", "").strip()
    if not key:
        print("FAL_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    workflows = _fetch_workflows(key, search="hotproducts")
    if not workflows:
        workflows = _fetch_workflows(key)

    if not workflows:
        print("No saved workflows on this FAL account yet.\n")
        print("You do NOT need a saved workflow for CLI runs. Use direct mode:")
        print("  python instagram/fal-workflow/run_batch.py --slug vitamix-7500\n")
        print("To create one in the FAL UI (optional, for --mode saved):")
        print("  1. Open https://fal.ai/workflows/new")
        print("  2. Add node: openrouter/router")
        print("     - prompt: $input.instagram_post")
        print("     - model: anthropic/claude-haiku-4.5")
        print("  3. Add node: fal-ai/flux/dev/image-to-image")
        print("     - image_url: $input.amazon_image_url")
        print("     - prompt: $node-prompt.output")
        print("     - strength: 0.35")
        print("  4. Add inputs: instagram_post (string), amazon_image_url (string)")
        print("  5. Save & Run, then re-run this script")
        print("\nOr import: instagram/fal-workflow/hotproducts-instagram-ad-creative.json")
        return

    _print_workflows(workflows)


if __name__ == "__main__":
    main()
