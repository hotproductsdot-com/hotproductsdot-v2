"""Validate the AI vision gate by running it against a known-bad banner
(Autonomous Standing Desk — scene with 8 accessories) and a known-good
banner (Husqvarna mower — clean isnet cutout). The bad banner should be
REJECTED with a specific reason. The good one should be APPROVED."""
import os
import sys

sys.path.insert(0, "/mnt/e/GITHUB/hotproductsdot-v2")
os.chdir("/mnt/e/GITHUB/hotproductsdot-v2")

from dotenv import load_dotenv

load_dotenv(override=True)

from instagram import banner_compose

# Compose a fresh standing-desk banner first (heuristic validators will pass).
desk = {
    "name": "Autonomous Standing Desk",
    "slug": "autonomous-standing-desk",
    "category": "Furniture",
    "rating": 4.7,
    "reviews": 461,
    "review_count": 461,
    "price": "169.99",
}
desk_src = "/mnt/e/GITHUB/hotproductsdot-v2/site/public/products/autonomous-standing-desk.jpg"
desk_out = "/tmp/banner_autonomous-standing-desk.jpg"

print("=== composing standing desk banner ===")
try:
    banner_compose.compose_banner(desk, desk_src, desk_out)
    print(f"composed → {desk_out}")
except banner_compose.BannerQualityError as exc:
    print(f"REJECTED at compose stage: {exc.reason}")
    sys.exit(0)

# (compose_banner now calls the AI gate internally; if it raised, we stopped above.)

print("\n=== ai gate on Husqvarna (should APPROVE) ===")
ok, reason = banner_compose._ai_vision_validate_banner(
    "/tmp/banner_husqvarna-automower-450x-robotic-lawn-mower.jpg",
    "Husqvarna Automower 450X Robotic Lawn Mower",
)
print(f"  approved={ok} reason={reason!r}")

print("\n=== ai gate on the original bad standing desk image (should REJECT) ===")
ok, reason = banner_compose._ai_vision_validate_banner(
    desk_out, "Autonomous Standing Desk"
)
print(f"  approved={ok} reason={reason!r}")
