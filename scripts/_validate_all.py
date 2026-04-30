"""Run the AI gate against all the banners we have on disk to confirm:
- Approved-good cases stay approved.
- Bad cases (Image #4 multi-product, Image #5 scene clutter) stay rejected.
- Unknown cases get useful verdicts."""
import os
import sys

sys.path.insert(0, "/mnt/e/GITHUB/hotproductsdot-v2")
os.chdir("/mnt/e/GITHUB/hotproductsdot-v2")

from dotenv import load_dotenv

load_dotenv(override=True)

from instagram import banner_compose

CASES = [
    ("/tmp/banner_husqvarna-automower-450x-robotic-lawn-mower.jpg",
     "Husqvarna Automower 450X Robotic Lawn Mower",
     "EXPECT APPROVE (clean isnet cutout)"),
    ("/tmp/banner_sony-a7r-v-camera.jpg",
     "Sony A7R V Camera",
     "EXPECT APPROVE (clean isnet cutout)"),
    ("/tmp/banner_horow-black-smart-toilet-with-pump-and-bidet-built-in.jpg",
     "HOROW Black Smart Toilet with Pump and Bidet Built In",
     "EXPECT APPROVE (clean isnet cutout from lifestyle source)"),
    ("/tmp/banner_shark-stratos-vacuum.jpg",
     "Shark Stratos Vacuum",
     "EXPECT APPROVE (largest-component crop fixed the multi-product collage)"),
    ("/tmp/banner_autonomous-standing-desk.jpg",
     "Autonomous Standing Desk",
     "EXPECT REJECT (scene clutter + OffiGo brand mismatch)"),
]

for path, name, expectation in CASES:
    print(f"\n{name}")
    print(f"  ({expectation})")
    if not os.path.exists(path):
        print(f"  SKIP (no file at {path})")
        continue
    ok, reason = banner_compose._ai_vision_validate_banner(path, name)
    status = "APPROVE" if ok else f"REJECT — {reason}"
    print(f"  -> {status}")
