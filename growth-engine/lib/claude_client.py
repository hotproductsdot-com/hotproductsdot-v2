"""Thin Anthropic SDK wrapper.

Exposes:
  - complete()          : free-form text with retry
  - complete_json()     : parse JSON from a text response (legacy)
  - complete_with_tool(): FORCED structured output via tool use — preferred
                          for any call that needs a guaranteed schema
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from anthropic import Anthropic, APIError, RateLimitError

from .config import CONFIG, is_dry_run, require_env


@dataclass
class ClaudeResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str

    @property
    def estimated_cost_usd(self) -> float:
        return (self.input_tokens / 1_000_000 * 3.0) + (
            self.output_tokens / 1_000_000 * 15.0
        )


_client: Optional[Anthropic] = None


def client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=require_env("ANTHROPIC_API_KEY"))
    return _client


def complete(
    system: str,
    user: str,
    *,
    model: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    max_retries: int = 4,
) -> ClaudeResponse:
    if is_dry_run():
        return ClaudeResponse(
            text=f"[DRY RUN] Would call Claude with system={len(system)}c user={len(user)}c",
            input_tokens=0,
            output_tokens=0,
            model=model or CONFIG["article"]["model"],
        )

    model = model or CONFIG["article"]["model"]
    backoff = 2.0
    last_err: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            resp = client().messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = "".join(
                block.text for block in resp.content if hasattr(block, "text")
            )
            return ClaudeResponse(
                text=text,
                input_tokens=resp.usage.input_tokens,
                output_tokens=resp.usage.output_tokens,
                model=resp.model,
            )
        except RateLimitError as e:
            last_err = e
            time.sleep(backoff)
            backoff *= 2
        except APIError as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(backoff)
                backoff *= 2
            else:
                raise
    raise RuntimeError(f"Claude failed after {max_retries} retries: {last_err}")


_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def extract_json(text: str) -> Any:
    m = _JSON_FENCE.search(text)
    if m:
        return json.loads(m.group(1))
    for opener, closer in [("{", "}"), ("[", "]")]:
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == opener:
                depth += 1
            elif text[i] == closer:
                depth -= 1
                if depth == 0:
                    return json.loads(text[start : i + 1])
    raise ValueError(f"No JSON found in response: {text[:200]}...")


def complete_json(
    system: str,
    user: str,
    *,
    model: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.4,
) -> Any:
    """Legacy text-mode JSON helper. Prefer complete_with_tool()."""
    resp = complete(
        system=system + "\n\nReply with JSON only, no prose, no fences.",
        user=user,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if is_dry_run():
        return {}
    return extract_json(resp.text)


def complete_with_tool(
    *,
    system: str,
    user: str,
    tool_name: str,
    tool_description: str,
    input_schema: Dict[str, Any],
    model: Optional[str] = None,
    max_tokens: int = 8000,
    temperature: float = 0.5,
    max_retries: int = 4,
) -> Dict[str, Any]:
    """Force Claude to call a single tool with a strict JSONSchema.
    Returns the dict that Claude passed as the tool's `input`. This is the
    most reliable way to get structured output from the model.
    """
    if is_dry_run():
        return {}

    model = model or CONFIG["article"]["model"]
    backoff = 2.0
    last_err: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            resp = client().messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                tools=[
                    {
                        "name": tool_name,
                        "description": tool_description,
                        "input_schema": input_schema,
                    }
                ],
                tool_choice={"type": "tool", "name": tool_name},
                messages=[{"role": "user", "content": user}],
            )
            for block in resp.content:
                # tool_use blocks expose `.input` (a dict)
                if getattr(block, "type", None) == "tool_use" and hasattr(block, "input"):
                    return block.input  # type: ignore[return-value]
                if hasattr(block, "input") and isinstance(getattr(block, "input"), dict):
                    return block.input  # type: ignore[return-value]
            raise RuntimeError(
                f"Claude returned no tool_use block. Content types: "
                f"{[getattr(b, 'type', type(b).__name__) for b in resp.content]}"
            )
        except RateLimitError as e:
            last_err = e
            time.sleep(backoff)
            backoff *= 2
        except APIError as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(backoff)
                backoff *= 2
            else:
                raise
    raise RuntimeError(f"Claude failed after {max_retries} retries: {last_err}")
