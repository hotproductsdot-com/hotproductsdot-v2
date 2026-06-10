#!/usr/bin/env python3
"""Validate a saved FAL workflow against HotProducts requirements."""
from __future__ import annotations

import argparse
import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

API_URL = "https://api.fal.ai/v1/workflows/{user}/{name}"


def _fetch(user: str, name: str) -> dict:
    key = os.environ.get("FAL_KEY", "").strip()
    if not key:
        print("FAL_KEY not set in .env", file=sys.stderr)
        sys.exit(1)
    resp = requests.get(
        API_URL.format(user=user, name=name),
        headers={"Authorization": f"Key {key}"},
        timeout=30,
    )
    if not resp.ok:
        print(f"API error {resp.status_code}: {resp.text[:500]}", file=sys.stderr)
        sys.exit(1)
    return resp.json()["workflow"]


def _parse_endpoint(endpoint: str) -> tuple[str, str]:
    # workflows/dennismcdaniel65/instagrampost
    parts = endpoint.strip("/").split("/")
    if len(parts) != 3 or parts[0] != "workflows":
        raise ValueError(f"Expected workflows/USER/NAME, got {endpoint!r}")
    return parts[1], parts[2]


def validate(workflow: dict) -> list[str]:
    issues: list[str] = []
    contents = workflow.get("contents") or {}
    nodes = contents.get("nodes") or {}
    schema_input = (contents.get("schema") or {}).get("input") or {}

    run_nodes = {k: v for k, v in nodes.items() if v.get("type") == "run"}
    llm_nodes = [n for n in run_nodes.values() if n.get("app") == "openrouter/router"]
    img_nodes = [
        n for n in run_nodes.values() if n.get("app") == "fal-ai/flux/dev/image-to-image"
    ]

    if not llm_nodes:
        issues.append("Missing openrouter/router node.")
    if not img_nodes:
        issues.append("Missing fal-ai/flux/dev/image-to-image node.")

    for node in llm_nodes:
        inp = node.get("input") or {}
        if inp.get("prompt") != "$input.instagram_post":
            issues.append(
                f"LLM node {node.get('id')}: prompt should be $input.instagram_post "
                f"(got {inp.get('prompt')!r})."
            )
        sys_prompt = (inp.get("system_prompt") or "").lower()
        if "caption" in sys_prompt and "image-to-image" not in sys_prompt:
            issues.append(
                f"LLM node {node.get('id')}: system_prompt writes captions, not img2img prompts."
            )

    for node in img_nodes:
        inp = node.get("input") or {}
        if not inp.get("prompt"):
            issues.append(
                f"Img2img node {node.get('id')}: missing prompt "
                "(required — wire from LLM output, e.g. $node-<llm-id>.output)."
            )
        if inp.get("image_url") != "$input.amazon_image_url":
            issues.append(
                f"Img2img node {node.get('id')}: image_url should be $input.amazon_image_url "
                f"(got {inp.get('image_url')!r})."
            )
        deps = node.get("depends") or []
        if llm_nodes and not any(
            llm["id"] in deps for llm in llm_nodes
        ):
            issues.append(
                f"Img2img node {node.get('id')}: must depend on the LLM node so prompt is ready."
            )

    required_inputs = {"instagram_post", "amazon_image_url"}
    missing = required_inputs - set(schema_input.keys())
    if missing:
        issues.append(f"Schema missing input fields: {sorted(missing)}")

    output = nodes.get("output") or {}
    if not output.get("depends"):
        issues.append("Output node has no depends — wire it to the img2img node.")
    fields = output.get("fields") or {}
    if not fields:
        issues.append("Output node has no fields — expose the generated image URL.")

    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workflow-endpoint",
        default=os.environ.get(
            "FAL_WORKFLOW_ENDPOINT", "workflows/dennismcdaniel65/instagrampost"
        ),
        help="workflows/USER/NAME",
    )
    args = parser.parse_args()

    user, name = _parse_endpoint(args.workflow_endpoint)
    workflow = _fetch(user, name)
    issues = validate(workflow)

    print(f"Workflow: {workflow.get('title')} ({args.workflow_endpoint})")
    if not issues:
        print("OK — workflow looks correctly wired.")
        return

    print("ISSUES:")
    for issue in issues:
        print(f"  - {issue}")
    print("\nFix in https://fal.ai/workflows/new (edit instagrampost), then Save & Run.")
    sys.exit(1)


if __name__ == "__main__":
    main()
