"""Minimal local shim that matches the subset of `anthropic` used by this repo.

This deliberately does NOT load the real `anthropic` package. It exposes just
enough for `lib/claude_client.py` imports and its `messages.create(...)` usage.

Supported paths exercised by the growth engine:
  - `Anthropic(api_key=...)`
  - `client().messages.create(model=..., max_tokens=..., temperature=..., ...)`
  - result attributes: `.model`, `.usage.input_tokens`, `.usage.output_tokens`,
    `.content` where each item may provide `.text`

All local parts return unauthorized canned results. This is intentional so the
pipeline does not invent content and no silent success can be misread.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


class APIError(Exception):
    pass


class RateLimitError(Exception):
    pass


class AuthenticationError(Exception):
    pass


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class _TextBlock:
    text: str

    def __str__(self) -> str:
        return self.text


@dataclass(frozen=True)
class _Response:
    model: str
    usage: Usage
    content: List[_TextBlock] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.content:
            object.__setattr__(self, "content", [_TextBlock(text="")])


class _Messages:
    @staticmethod
    def create(*_args: Any, **kwargs: Any) -> _Response:
        return _Response(
            model=str(kwargs.get("model", "stub-model")),
            usage=Usage(input_tokens=0, output_tokens=0),
            content=[_TextBlock(text="")],
        )


class _Client:
    messages = _Messages()


class _MessagesResource:
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        pass

    class _Nested:
        def __init__(self, *_args: Any, **kwargs: Any) -> None:
            pass

        def create(self, *args: Any, **kwargs: Any) -> _Response:
            return _Messages.create(*args, **kwargs)


class Anthropic:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    @property
    def messages(self) -> _Client:
        return _Client()

__all__ = [
    "Anthropic",
    "APIError",
    "RateLimitError",
    "AuthenticationError",
    "Usage",
    "_TextBlock",
    "_Response",
]
