"""
pinterest_poster.py — stub mirroring the shape of instagram/poster.py

Status: SKELETON. Wire up after Pinterest API approval.
Apply at: https://developers.pinterest.com (3-5 day approval)

Once approved you'll get an OAuth client_id/client_secret and can:
  1. Run a one-time auth flow to get an access token
  2. POST pins via /v5/pins endpoint
  3. List boards via /v5/boards

Until approval: use Pinterest's built-in scheduler in the web UI (free,
schedules ~100 pins ~2 weeks ahead). See CONTENT_CALENDAR.md for the
batch workflow.
"""

from __future__ import annotations
import os
import json
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Will need: pip install requests
# import requests

PINTEREST_API_BASE = "https://api.pinterest.com/v5"

# UTM template — see PINTEREST_PLAYBOOK.md "Step 4 — UTM tagging"
SITE_UTM_TEMPLATE = (
    "?utm_source=pinterest"
    "&utm_medium=social"
    "&utm_campaign={campaign}"
    "&utm_content=pin-{slug}"
)
AMAZON_SUBTAG_TEMPLATE = "&ascsubtag=pin-{board}-{date}"


@dataclass
class PinDraft:
    title: str               # ≤40 char — see PIN_DESCRIPTIONS.md formulas
    description: str         # ≤500 char — use the 5-part formula
    image_path: Path         # 1000x1500 PNG/JPG
    destination_url: str     # post-UTM-tagged
    board_id: str            # Pinterest board ID (fetch via /v5/boards)
    alt_text: str            # accessibility + SEO


def build_destination_url(
    site_path: str | None = None,
    amazon_url: str | None = None,
    campaign: str = "general",
    slug: str = "pin",
    board: str = "general",
    date: str = "20260424",
) -> str:
    """
    Build a tracked destination URL.

    70/30 rule (see PINTEREST_PLAYBOOK.md):
    - 70% of pins: site_path → /best/<category> or /products/<slug>
      (which already enforces affiliate tag via buildAffiliateUrl)
    - 30% of pins: direct amazon_url with ascsubtag

    Pass exactly one of site_path or amazon_url.
    """
    if site_path and amazon_url:
        raise ValueError("Pass only one of site_path or amazon_url")

    if site_path:
        utm = SITE_UTM_TEMPLATE.format(campaign=campaign, slug=slug)
        return f"https://hotproductsdot.com{site_path}{utm}"

    if amazon_url:
        sep = "&" if "?" in amazon_url else "?"
        # Ensure affiliate tag present (matches site/app/lib/affiliate.ts)
        if "tag=" not in amazon_url:
            amazon_url = f"{amazon_url}{sep}tag=hotproduct033-20"
            sep = "&"
        subtag = AMAZON_SUBTAG_TEMPLATE.format(board=board, date=date)
        return amazon_url + subtag

    raise ValueError("Must pass site_path or amazon_url")


def post_pin(draft: PinDraft, access_token: str) -> dict:
    """
    POST /v5/pins  — create a pin on a board.
    Docs: https://developers.pinterest.com/docs/api/v5/pins-create
    """
    raise NotImplementedError(
        "Apply for Pinterest API access at developers.pinterest.com first."
    )
    # Reference shape:
    # url = f"{PINTEREST_API_BASE}/pins"
    # headers = {"Authorization": f"Bearer {access_token}"}
    # # Image is multipart upload OR base64 OR public URL
    # payload = {
    #     "board_id": draft.board_id,
    #     "title": draft.title,
    #     "description": draft.description,
    #     "alt_text": draft.alt_text,
    #     "link": draft.destination_url,
    #     "media_source": {
    #         "source_type": "image_url",
    #         "url": "https://hotproductsdot.com/products/<image>.jpg",
    #     },
    # }
    # r = requests.post(url, json=payload, headers=headers)
    # r.raise_for_status()
    # return r.json()


def load_boards_from_csv(csv_path: Path = Path("pinterest-setup/BOARDS.csv")) -> list[dict]:
    """Read the BOARDS.csv into a list of dicts. Useful for batch operations."""
    with open(csv_path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def example_workflow():
    """
    Example: pull tomorrow's pins from CONTENT_CALENDAR + post them.
    Wire this into post_daily.py once API access is granted.
    """
    boards = load_boards_from_csv()
    print(f"Loaded {len(boards)} boards from CSV")

    # Site-pin example (preferred, 70% of pins):
    url1 = build_destination_url(
        site_path="/best/kitchen",
        campaign="kitchen-launch-week1",
        slug="air-fryer-roundup",
    )
    print("Site pin destination:", url1)

    # Direct-Amazon example (30% of pins, hot/seasonal items):
    url2 = build_destination_url(
        amazon_url="https://www.amazon.com/dp/B0XXXXX?tag=hotproduct033-20",
        board="best-kitchen-gadgets-2026",
        date="20260427",
    )
    print("Direct Amazon destination:", url2)


if __name__ == "__main__":
    example_workflow()
