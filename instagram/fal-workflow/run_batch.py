#!/usr/bin/env python3
"""Run the HotProducts FAL workflow for each product preset."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(override=True)

WORKFLOW_DIR = Path(__file__).resolve().parent
PRODUCTS_JSON = WORKFLOW_DIR / "products.json"

LLM_MODEL = "anthropic/claude-haiku-4.5"
SYSTEM_PROMPT = (
    "You are an e-commerce ad creative director for @hotproductsdot.official on Instagram. "
    "Given an Instagram post caption (hook, product name, category, rating, price, CTA), "
    "write ONE photorealistic image-to-image prompt for FLUX. The prompt must restyle the "
    "attached Amazon product photo into a premium square marketing asset. Rules: reproduce "
    "the product faithfully (exact shape, color, branding, proportions); square 1:1 framing "
    "with hero product centered; premium studio look with soft shadow and clean dark charcoal "
    "backdrop plus subtle warm orange (#FF6B00) glow; photorealistic only; NO text, logos, "
    "watermarks, or captions in the image; leave ~30% breathing room for post-processing "
    "headline and CTA. Output ONLY the prompt text, no preamble or quotes."
)
IMG2IMG_MODEL = "fal-ai/flux/dev/image-to-image"


def _require_fal_client():
    try:
        import fal_client
    except ImportError:
        print("Install fal_client: pip install fal-client", file=sys.stderr)
        sys.exit(1)
    if not os.environ.get("FAL_KEY"):
        print("FAL_KEY not set in .env", file=sys.stderr)
        sys.exit(1)
    return fal_client


def _product_args(product: dict) -> dict[str, str]:
    return {
        "instagram_post": product["instagram_post"],
        "amazon_image_url": product["amazon_image_url"],
    }


def _run_direct(product: dict) -> dict[str, Any]:
    """Chain LLM + img2img directly — same graph as the FAL UI workflow."""
    fal_client = _require_fal_client()
    args = _product_args(product)

    llm = fal_client.subscribe(
        "openrouter/router",
        arguments={
            "model": LLM_MODEL,
            "prompt": args["instagram_post"],
            "system_prompt": SYSTEM_PROMPT,
            "max_tokens": 500,
            "temperature": 0.35,
        },
    )
    prompt = (llm.get("output") or "").strip()
    if not prompt:
        raise RuntimeError(f"LLM returned empty prompt: {llm!r}")

    img = fal_client.subscribe(
        IMG2IMG_MODEL,
        arguments={
            "image_url": args["amazon_image_url"],
            "prompt": prompt,
            "strength": 0.35,
            "num_inference_steps": 28,
            "guidance_scale": 3.5,
            "num_images": 1,
            "output_format": "jpeg",
            "enable_safety_checker": True,
        },
    )
    images = img.get("images") or []
    if not images:
        raise RuntimeError(f"img2img returned no images: {img!r}")

    return {
        "prompt": prompt,
        "image": images[0].get("url"),
        "images": images,
    }


def _run_saved_workflow(endpoint: str, product: dict) -> dict[str, Any]:
    """Call a workflow saved in the FAL UI: workflows/{user}/{name}."""
    fal_client = _require_fal_client()
    return fal_client.subscribe(endpoint, arguments=_product_args(product))


def _extract_image(result: dict[str, Any]) -> str | None:
    if result.get("image"):
        return result["image"]
    images = result.get("images")
    if isinstance(images, list) and images:
        return images[0].get("url")
    output = result.get("output")
    if isinstance(output, dict):
        if output.get("image"):
            return output["image"]
        out_images = output.get("images")
        if isinstance(out_images, list) and out_images:
            return out_images[0].get("url")
    return None


def _run_one(
    product: dict,
    *,
    dry_run: bool,
    mode: str,
    workflow_endpoint: str | None,
) -> dict[str, Any] | None:
    if dry_run:
        print(f"  [dry-run] {product['slug']}")
        print(f"    amazon_image_url: {product['amazon_image_url']}")
        return {"dry_run": True, "slug": product["slug"]}

    if mode == "saved":
        if not workflow_endpoint:
            raise ValueError(
                "mode=saved requires a real workflow endpoint. "
                "Save the workflow in the FAL UI first, then run: "
                "python instagram/fal-workflow/list_workflows.py"
            )
        if "YOUR_USER" in workflow_endpoint.upper():
            raise ValueError(
                f"Replace the README placeholder with your real endpoint. "
                f"Got: {workflow_endpoint!r}. "
                "Or skip workflow creation and use default mode: "
                "python instagram/fal-workflow/run_batch.py --slug <slug>"
            )
        return _run_saved_workflow(workflow_endpoint, product)
    return _run_direct(product)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print inputs only")
    parser.add_argument("--slug", help="Run a single product slug")
    parser.add_argument(
        "--mode",
        choices=("direct", "saved"),
        default="direct",
        help=(
            "direct: chain openrouter + flux models (default); "
            "saved: call workflow saved in FAL UI"
        ),
    )
    parser.add_argument(
        "--workflow-endpoint",
        default=os.environ.get("FAL_WORKFLOW_ENDPOINT", ""),
        help="Saved workflow id for --mode saved (env: FAL_WORKFLOW_ENDPOINT)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=WORKFLOW_DIR / "results.json",
        help="Write batch results JSON here",
    )
    args = parser.parse_args()

    catalog = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))
    products = catalog["products"]
    if args.slug:
        products = [p for p in products if p["slug"] == args.slug]
        if not products:
            print(f"No product with slug {args.slug!r}", file=sys.stderr)
            sys.exit(1)

    workflow_endpoint = args.workflow_endpoint.strip() or None
    results: list[dict] = []
    for product in products:
        print(f"Running {product['slug']} (mode={args.mode})...")
        try:
            out = _run_one(
                product,
                dry_run=args.dry_run,
                mode=args.mode,
                workflow_endpoint=workflow_endpoint,
            )
            results.append({"slug": product["slug"], "ok": True, "result": out})
            if not args.dry_run and out:
                image = _extract_image(out)
                if image:
                    print(f"  OK: {image}")
        except Exception as exc:
            print(f"  FAILED: {exc}")
            results.append({"slug": product["slug"], "ok": False, "error": str(exc)})

    if not args.dry_run:
        args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Wrote results to {args.out}")


if __name__ == "__main__":
    main()
