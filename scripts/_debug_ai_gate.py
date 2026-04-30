"""Print the raw response from the vision model to diagnose why the bad
standing-desk banner is being approved."""
import base64
import os
import sys

sys.path.insert(0, "/mnt/e/GITHUB/hotproductsdot-v2")
os.chdir("/mnt/e/GITHUB/hotproductsdot-v2")

from dotenv import load_dotenv

load_dotenv(override=True)

import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

with open("/tmp/banner_autonomous-standing-desk.jpg", "rb") as f:
    jpg_b64 = base64.standard_b64encode(f.read()).decode("ascii")

prompt = """You are an unforgiving QA reviewer for a brand Instagram account.
The banner below has the product title: "Autonomous Standing Desk".

Walk through these checks IN ORDER and write your findings to the "checks" object. After each check, decide approve/reject. Only set approved=true if EVERY check passes. Default to rejecting when uncertain.

CHECK 1 — Single product (no duplicates): Count distinct instances.
CHECK 2 — Scene clutter: List every NON-product object visible.
CHECK 3 — Brand identity: Read every visible logo/text on objects.
CHECK 4 — Cutout artifacts: Jagged edges, halo, partial erasure.

Reply with ONLY a single JSON object, no markdown fences, no preamble:
{"checks": {"check1": "...", "check2": "...", "check3": "...", "check4": "..."}, "approved": true|false, "reason": "..."}"""

for model in ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"]:
    print(f"\n=== model: {model} ===")
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=600,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": jpg_b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        print(msg.content[0].text)
    except Exception as exc:
        print(f"  ERROR ({type(exc).__name__}): {exc}")
