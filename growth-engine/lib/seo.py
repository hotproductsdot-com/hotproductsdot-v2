"""SERP + web search utilities. Tries Tavily, falls back to Serper, falls back
to Claude's own web knowledge if no key is present (lower quality, free).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

import requests


@dataclass
class SerpResult:
    title: str
    url: str
    snippet: str


def _tavily(query: str, max_results: int = 8) -> List[SerpResult]:
    key = os.getenv("TAVILY_API_KEY", "").strip()
    if not key:
        return []
    try:
        r = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": key,
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
            },
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []
    return [
        SerpResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("content", ""),
        )
        for item in data.get("results", [])
    ]


def _serper(query: str, max_results: int = 8) -> List[SerpResult]:
    key = os.getenv("SERPER_API_KEY", "").strip()
    if not key:
        return []
    try:
        r = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            json={"q": query, "num": max_results},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []
    out: List[SerpResult] = []
    for item in (data.get("organic") or [])[:max_results]:
        out.append(
            SerpResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
            )
        )
    return out


def search(query: str, max_results: int = 8) -> List[SerpResult]:
    """Best-available SERP. Returns [] if no provider configured."""
    return _tavily(query, max_results) or _serper(query, max_results)


def has_search_provider() -> bool:
    return bool(os.getenv("TAVILY_API_KEY") or os.getenv("SERPER_API_KEY"))
