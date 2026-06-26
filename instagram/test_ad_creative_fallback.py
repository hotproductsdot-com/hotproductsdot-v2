"""Regression tests for the white-box bug (2026-06-10).

The --ad-creative pipeline silently fell back to the white-card banner
whenever FAL generation couldn't run (fal_client missing, FAL_KEY unset,
or the FAL call failing). The fallback shipped "white box" posts to
Instagram with no operator-visible signal.

These tests pin the fixed contract:
  - FAL failure raises AdCreativeError by default (no silent white card).
  - AD_CREATIVE_FALLBACK=white-card restores the old fallback explicitly.
  - A missing FAL_KEY fails fast, before any Tavily spend.
  - Tavily reference images are actually passed to FAL (the prompt
    promises them; they used to be fetched and dropped).

Run: venv/bin/python -m pytest instagram/test_ad_creative_fallback.py
"""
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from instagram import ad_creative_gen
from instagram import image_gen_fal


def _jpeg_bytes(color: tuple[int, int, int] = (200, 30, 30), size: int = 64) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (size, size), color).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture()
def product() -> dict:
    return {
        "name": "Test Product",
        "category": "Gadgets",
        "price": "19.99",
        "rating": 4.5,
        "reviews": "120",
    }


@pytest.fixture()
def src_jpg(tmp_path: Path) -> str:
    p = tmp_path / "src.jpg"
    p.write_bytes(_jpeg_bytes())
    return str(p)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BANNER_AI_GATE", "off")
    monkeypatch.setenv("FAL_KEY", "test-key")
    monkeypatch.delenv("AD_CREATIVE_FALLBACK", raising=False)


def test_fal_failure_raises_by_default(monkeypatch, tmp_path, product, src_jpg):
    """FAL returning no image must raise, not silently post a white card."""
    monkeypatch.setattr(ad_creative_gen, "_tavily_image_urls", lambda q, n: [])
    monkeypatch.setattr(image_gen_fal, "_fal_generate_image", lambda *a, **k: None)
    out = tmp_path / "banner.jpg"

    with pytest.raises(ad_creative_gen.AdCreativeError):
        ad_creative_gen.compose_ad_creative_banner(product, src_jpg, out)
    assert not out.exists(), "no banner may be written when generation fails"


def test_white_card_fallback_is_explicit_opt_in(monkeypatch, tmp_path, product, src_jpg):
    """AD_CREATIVE_FALLBACK=white-card restores the legacy fallback."""
    monkeypatch.setenv("AD_CREATIVE_FALLBACK", "white-card")
    monkeypatch.setattr(ad_creative_gen, "_tavily_image_urls", lambda q, n: [])
    monkeypatch.setattr(image_gen_fal, "_fal_generate_image", lambda *a, **k: None)
    calls: list[tuple] = []

    def fake_compose_banner(prod, src, out_path, *a, **k):
        calls.append((prod, src))
        Path(out_path).write_bytes(b"jpg")
        return str(out_path)

    monkeypatch.setattr(ad_creative_gen, "compose_banner", fake_compose_banner)
    out = tmp_path / "banner.jpg"

    result = ad_creative_gen.compose_ad_creative_banner(product, src_jpg, out)

    assert result == str(out)
    assert len(calls) == 1, "white-card pipeline must be used exactly once"


def test_missing_fal_key_fails_fast_before_tavily(monkeypatch, tmp_path, product, src_jpg):
    """Without FAL_KEY the pipeline must not spend Tavily credits."""
    monkeypatch.delenv("FAL_KEY", raising=False)

    def tavily_must_not_run(q, n):
        raise AssertionError("Tavily was called despite FAL being unavailable")

    monkeypatch.setattr(ad_creative_gen, "_tavily_image_urls", tavily_must_not_run)

    with pytest.raises(ad_creative_gen.AdCreativeError, match="FAL_KEY"):
        ad_creative_gen.compose_ad_creative_banner(
            product, src_jpg, tmp_path / "banner.jpg"
        )


def test_reference_images_are_passed_to_fal(monkeypatch, tmp_path, product, src_jpg):
    """Tavily references must reach FAL — the prompt tells the model they exist."""
    ref_a = tmp_path / "ref_a.jpg"
    ref_b = tmp_path / "ref_b.jpg"
    ref_a.write_bytes(_jpeg_bytes((30, 200, 30)))
    ref_b.write_bytes(_jpeg_bytes((30, 30, 200)))
    monkeypatch.setattr(
        ad_creative_gen, "_tavily_image_urls", lambda q, n: [str(ref_a), str(ref_b)]
    )
    captured: dict = {}

    def fake_generate(prompt, base_image_bytes, reference_images=()):
        captured["references"] = list(reference_images)
        return _jpeg_bytes((10, 10, 10), size=1080)

    monkeypatch.setattr(image_gen_fal, "_fal_generate_image", fake_generate)
    out = tmp_path / "banner.jpg"

    result = ad_creative_gen.compose_ad_creative_banner(product, src_jpg, out)

    assert result == str(out)
    assert out.exists()
    assert len(captured["references"]) == 2, "both usable references must be forwarded"


def test_identity_mismatch_blocks_generated_creative(monkeypatch, tmp_path, product, src_jpg):
    """A polished but wrong img2img result must be quarantined before upload."""
    monkeypatch.setenv("BANNER_AI_GATE", "enforce")
    monkeypatch.setattr(ad_creative_gen, "_tavily_image_urls", lambda q, n: [])
    monkeypatch.setattr(
        image_gen_fal,
        "_fal_generate_image",
        lambda *a, **k: _jpeg_bytes((10, 10, 10), size=1080),
    )
    monkeypatch.setattr(
        ad_creative_gen,
        "_ai_validate_product_identity",
        lambda *a, **k: (False, "generated product does not match source"),
    )
    out = tmp_path / "banner.jpg"

    with pytest.raises(ad_creative_gen.BannerQualityError, match="ai identity"):
        ad_creative_gen.compose_ad_creative_banner(product, src_jpg, out)

    assert not out.exists(), "wrong-product creative must not be written or uploaded"
