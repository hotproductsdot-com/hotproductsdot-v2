"""Tests for the ScrapeCreators competitor-ad fetcher.

Run as a module: ``venv/bin/python -m pytest instagram/test_competitor_ads.py -v``
or as a script:  ``venv/bin/python instagram/test_competitor_ads.py``

The live-API test is opt-in via ``RUN_LIVE_SCRAPECREATORS=1`` so CI never
burns API credits.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from instagram import competitor_ads


SAMPLE_PAYLOAD = {
    "searchResults": [
        {
            "ad_archive_id": "615470338018648",
            "is_active": True,
            "page_name": "Acme Outdoors",
            "snapshot": {
                "current_page_name": "Acme Outdoors",
                "title": "Best running shoes",
                "body": {"text": "Performance trail runners on sale."},
                "cta_text": "Shop Now",
                "cta_type": "SHOP_NOW",
                "display_format": "IMAGE",
                "images": [
                    {
                        "original_image_url": "https://cdn.example.com/orig1.jpg",
                        "resized_image_url": "https://cdn.example.com/600x600/r1.jpg",
                    }
                ],
            },
        },
        {
            "ad_archive_id": "888075953335279",
            "is_active": True,
            "page_name": "Beta Gear",
            "snapshot": {
                "title": "",
                "body": {"text": ""},
                "images": [
                    {
                        "original_image_url": "https://cdn.example.com/orig2.jpg",
                        "resized_image_url": None,
                    }
                ],
            },
        },
        {
            # No images at all — must be filtered out by _normalize.
            "ad_archive_id": "no-image",
            "snapshot": {"images": []},
        },
    ],
    "searchResultsCount": 50001,
    "cursor": "AQHRYL...",
}


@pytest.fixture
def with_api_key():
    prev = os.environ.get("SCRAPECREATORS_API_KEY")
    os.environ["SCRAPECREATORS_API_KEY"] = "test_key_xxx"
    yield
    if prev is None:
        os.environ.pop("SCRAPECREATORS_API_KEY", None)
    else:
        os.environ["SCRAPECREATORS_API_KEY"] = prev


@pytest.fixture
def without_api_key():
    prev = os.environ.pop("SCRAPECREATORS_API_KEY", None)
    yield
    if prev is not None:
        os.environ["SCRAPECREATORS_API_KEY"] = prev


def _mock_response(payload: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    resp.raise_for_status = MagicMock(
        side_effect=None if status < 400 else Exception(f"HTTP {status}")
    )
    return resp


class TestFetchCompetitorAds:
    """fetch_competitor_ads: input handling and normalization."""

    def test_missing_key_returns_empty(self, without_api_key):
        result = competitor_ads.fetch_competitor_ads("Anker")
        assert result == []

    def test_blank_query_returns_empty(self, with_api_key):
        assert competitor_ads.fetch_competitor_ads("") == []
        assert competitor_ads.fetch_competitor_ads("   ") == []

    def test_normalizes_payload(self, with_api_key):
        with patch("instagram.competitor_ads.requests.get") as g:
            g.return_value = _mock_response(SAMPLE_PAYLOAD)
            ads = competitor_ads.fetch_competitor_ads("running", limit=5)

        # Third row has no images → filtered out.
        assert len(ads) == 2
        first, second = ads
        assert first.archive_id == "615470338018648"
        assert first.page_name == "Acme Outdoors"
        # resized_image_url preferred when present.
        assert first.image_urls == ("https://cdn.example.com/600x600/r1.jpg",)
        assert first.title == "Best running shoes"
        assert "Performance trail runners" in first.body
        assert first.cta_text == "Shop Now"
        assert first.is_active is True
        # Falls back to original_image_url when resized is None.
        assert second.image_urls == ("https://cdn.example.com/orig2.jpg",)

    def test_limit_caps_results(self, with_api_key):
        with patch("instagram.competitor_ads.requests.get") as g:
            g.return_value = _mock_response(SAMPLE_PAYLOAD)
            ads = competitor_ads.fetch_competitor_ads("running", limit=1)
        assert len(ads) == 1

    def test_passes_required_query_params(self, with_api_key):
        with patch("instagram.competitor_ads.requests.get") as g:
            g.return_value = _mock_response(SAMPLE_PAYLOAD)
            competitor_ads.fetch_competitor_ads("running shoes")
        called = g.call_args
        assert called.args[0] == competitor_ads.ENDPOINT
        assert called.kwargs["headers"] == {"x-api-key": "test_key_xxx"}
        assert called.kwargs["params"]["query"] == "running shoes"
        assert called.kwargs["params"]["status"] == "ACTIVE"
        assert called.kwargs["params"]["sort_by"] == "total_impressions"

    def test_http_error_returns_empty(self, with_api_key):
        with patch("instagram.competitor_ads.requests.get") as g:
            err_resp = MagicMock()
            err_resp.raise_for_status.side_effect = requests.HTTPError(
                "500 server error"
            )
            g.return_value = err_resp
            ads = competitor_ads.fetch_competitor_ads("running")
        assert ads == []

    def test_connection_error_returns_empty(self, with_api_key):
        with patch("instagram.competitor_ads.requests.get") as g:
            g.side_effect = requests.ConnectionError("network down")
            ads = competitor_ads.fetch_competitor_ads("running")
        assert ads == []

    def test_malformed_json_returns_empty(self, with_api_key):
        with patch("instagram.competitor_ads.requests.get") as g:
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.side_effect = ValueError("not json")
            g.return_value = resp
            ads = competitor_ads.fetch_competitor_ads("running")
        assert ads == []

    def test_empty_results_returns_empty(self, with_api_key):
        with patch("instagram.competitor_ads.requests.get") as g:
            g.return_value = _mock_response({"searchResults": []})
            ads = competitor_ads.fetch_competitor_ads("running")
        assert ads == []


class TestCollectReferenceImageUrls:
    """collect_reference_image_urls: flat-URL view used by ad_creative_gen."""

    def test_zero_n_returns_empty(self, with_api_key):
        assert competitor_ads.collect_reference_image_urls("running", 0) == []

    def test_flattens_and_caps(self, with_api_key):
        with patch("instagram.competitor_ads.requests.get") as g:
            g.return_value = _mock_response(SAMPLE_PAYLOAD)
            urls = competitor_ads.collect_reference_image_urls("running", 4)
        assert urls == [
            "https://cdn.example.com/600x600/r1.jpg",
            "https://cdn.example.com/orig2.jpg",
        ]

    def test_caps_below_available(self, with_api_key):
        with patch("instagram.competitor_ads.requests.get") as g:
            g.return_value = _mock_response(SAMPLE_PAYLOAD)
            urls = competitor_ads.collect_reference_image_urls("running", 1)
        assert len(urls) == 1


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_SCRAPECREATORS") != "1",
    reason="live API call — set RUN_LIVE_SCRAPECREATORS=1 to run",
)
class TestLiveAPI:
    """Opt-in live call to validate the live ScrapeCreators contract."""

    def test_live_anker_search(self):
        from dotenv import load_dotenv

        load_dotenv()
        ads = competitor_ads.fetch_competitor_ads("Anker", limit=3)
        assert isinstance(ads, list)
        for ad in ads:
            assert ad.archive_id
            assert ad.image_urls
            for url in ad.image_urls:
                assert url.startswith("http")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
