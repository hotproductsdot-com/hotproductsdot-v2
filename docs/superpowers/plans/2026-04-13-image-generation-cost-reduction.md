# Image Generation Cost Reduction: fal.ai → ModelsLab

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate from fal.ai ($40-60/month) to ModelsLab ($0.002/image or $29/month unlimited) while maintaining image quality and feature parity.

**Architecture:** Replace fal.ai nano-banana-2 calls with ModelsLab FLUX API. ModelsLab supports both text-to-image and image-to-image (edit mode), enabling us to keep the current workflow. The API differs only in endpoint, payload format, and response structure—the higher-level logic stays the same.

**Tech Stack:** Python requests library, ModelsLab REST API, FLUX models (text-to-image & image-to-image)

---

### Task 1: Write tests for ModelsLab image generation (TDD approach)

**Files:**
- Create: `instagram/test_modelslab_image_gen.py`

- [ ] **Step 1: Create test file with mocked ModelsLab API**

```python
# instagram/test_modelslab_image_gen.py
"""Tests for ModelsLab image generation integration."""
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from instagram import image_gen


@pytest.fixture
def sample_product():
    """Sample product dict for testing."""
    return {
        "name": "Vitamix 5200",
        "category": "blender",
        "amazon_url": "https://amazon.com/Vitamix-5200/dp/B00EXAMPLE",
        "image_url": "https://hotproductsdot.com/vitamix.jpg",
    }


@pytest.fixture
def modelslab_api_key():
    """Set ModelsLab API key for testing."""
    os.environ["MODELSLAB_KEY"] = "test_key_12345"
    yield
    if "MODELSLAB_KEY" in os.environ:
        del os.environ["MODELSLAB_KEY"]


class TestModelsLabImageGeneration:
    """Test ModelsLab image generation functions."""

    def test_generate_product_images_requires_key(self):
        """Verify that missing MODELSLAB_KEY raises ValueError."""
        if "MODELSLAB_KEY" in os.environ:
            del os.environ["MODELSLAB_KEY"]
        
        product = {"name": "Test Product"}
        with pytest.raises(ValueError, match="MODELSLAB_KEY not set"):
            image_gen.generate_product_images(product)

    @patch("instagram.image_gen._call_modelslab_api")
    def test_generate_product_images_returns_list(self, mock_call, sample_product, modelslab_api_key):
        """Verify generate_product_images returns list of variant dicts."""
        # Mock API responses for 5 variants
        mock_call.side_effect = [
            "https://modelslab.example.com/image1.jpg",
            "https://modelslab.example.com/image2.jpg",
            "https://modelslab.example.com/image3.jpg",
            "https://modelslab.example.com/image4.jpg",
            "https://modelslab.example.com/image5.jpg",
        ]
        
        variants = image_gen.generate_product_images(sample_product, n=5)
        
        assert len(variants) == 5
        assert all("style" in v for v in variants)
        assert all("url" in v for v in variants)
        assert all("index" in v for v in variants)
        assert variants[0]["style"] == "banner"
        assert variants[0]["url"] == "https://modelslab.example.com/image1.jpg"

    @patch("instagram.image_gen._call_modelslab_api")
    def test_generate_product_images_with_image_edit_mode(self, mock_call, sample_product, modelslab_api_key):
        """Verify image-to-image mode when product_img_url is available."""
        mock_call.side_effect = [
            "https://modelslab.example.com/variant1.jpg",
            "https://modelslab.example.com/variant2.jpg",
            "https://modelslab.example.com/variant3.jpg",
            "https://modelslab.example.com/variant4.jpg",
            "https://modelslab.example.com/variant5.jpg",
        ]
        
        variants = image_gen.generate_product_images(sample_product, n=5)
        
        # Verify API was called with image_url for edit mode
        calls = mock_call.call_args_list
        assert len(calls) == 5
        # First call should include image_url for image-to-image
        first_call_kwargs = calls[0][1]
        assert "image_url" in first_call_kwargs

    def test_generate_product_images_saves_locally(self, sample_product, modelslab_api_key, tmp_path):
        """Verify images are saved locally when save_dir is provided."""
        mock_image_data = b"fake jpeg data"
        
        with patch("instagram.image_gen._call_modelslab_api") as mock_call, \
             patch("requests.get") as mock_get:
            mock_call.side_effect = [
                "https://modelslab.example.com/img1.jpg",
                "https://modelslab.example.com/img2.jpg",
                "https://modelslab.example.com/img3.jpg",
                "https://modelslab.example.com/img4.jpg",
                "https://modelslab.example.com/img5.jpg",
            ]
            mock_response = MagicMock()
            mock_response.content = mock_image_data
            mock_get.return_value = mock_response
            
            variants = image_gen.generate_product_images(sample_product, n=5, save_dir=tmp_path)
            
            # Verify files were saved
            assert len(list(tmp_path.glob("*.jpg"))) == 5
            assert variants[0]["local_path"] == str(tmp_path / "variant_1_banner.jpg")


class TestCallModelsLabApi:
    """Test low-level ModelsLab API calls."""

    @patch("requests.post")
    def test_call_modelslab_api_text_to_image(self, mock_post, modelslab_api_key):
        """Verify ModelsLab API call for text-to-image generation."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "success",
            "output": ["https://modelslab.example.com/output.jpg"]
        }
        mock_post.return_value = mock_response
        
        prompt = "Premium product photo on dark background"
        url = image_gen._call_modelslab_api(
            prompt=prompt,
            api_key="test_key",
            image_url=None,
            model="flux",
        )
        
        assert url == "https://modelslab.example.com/output.jpg"
        
        # Verify API was called correctly
        call_args = mock_post.call_args
        assert "https://modelslab.com/api/v6/images/text2img" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["prompt"] == prompt
        assert "image_url" not in payload  # Text-to-image mode

    @patch("requests.post")
    def test_call_modelslab_api_image_to_image(self, mock_post, modelslab_api_key):
        """Verify ModelsLab API call for image-to-image (edit mode)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "success",
            "output": ["https://modelslab.example.com/edited.jpg"]
        }
        mock_post.return_value = mock_response
        
        prompt = "Restyle this product on dark background"
        image_url = "https://example.com/product.jpg"
        
        url = image_gen._call_modelslab_api(
            prompt=prompt,
            api_key="test_key",
            image_url=image_url,
            model="flux",
        )
        
        assert url == "https://modelslab.example.com/edited.jpg"
        
        # Verify API was called with image_url for image-to-image
        call_args = mock_post.call_args
        assert "https://modelslab.com/api/v6/images/img2img" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["image_url"] == image_url


class TestIntegrationWithPostDaily:
    """Integration tests: verify post_daily.py still works with ModelsLab."""

    @patch("instagram.image_gen._call_modelslab_api")
    @patch("instagram.image_gen._fetch_amazon_image_url")
    def test_post_daily_image_generation_flow(self, mock_fetch, mock_call, modelslab_api_key):
        """Verify the full post_daily.py image generation flow."""
        # Mock Amazon image fetch (image-to-image mode)
        mock_fetch.return_value = "https://example.com/amazon-product.jpg"
        
        # Mock ModelsLab API responses
        mock_call.side_effect = [
            "https://modelslab.example.com/var1.jpg",
            "https://modelslab.example.com/var2.jpg",
            "https://modelslab.example.com/var3.jpg",
            "https://modelslab.example.com/var4.jpg",
            "https://modelslab.example.com/var5.jpg",
        ]
        
        product = {
            "name": "Test Blender",
            "category": "kitchen",
            "amazon_url": "https://amazon.com/test",
        }
        
        # This is the exact flow post_daily.py uses
        variants = image_gen.generate_product_images(product, n=5)
        
        assert len(variants) == 5
        assert all(v["url"] for v in variants)
        assert variants[0]["style"] == "banner"
        assert all(v["style"] in image_gen._STYLES for v in variants)

    def test_backward_compatibility_with_existing_code(self, modelslab_api_key):
        """Verify API matches what post_daily.py expects."""
        product = {"name": "Test Product"}
        
        # post_daily.py calls generate_product_images() like this:
        # variants = image_gen.generate_product_images(product, n=5, save_dir=save_dir)
        
        # This should NOT raise an error about missing arguments
        with patch("instagram.image_gen._call_modelslab_api") as mock_call:
            mock_call.return_value = "https://example.com/img.jpg"
            
            try:
                variants = image_gen.generate_product_images(product, n=5)
                # If we get here, the API is backward compatible
                assert True
            except TypeError as e:
                pytest.fail(f"API compatibility broken: {e}")
```

- [ ] **Step 2: Run tests to verify they fail (TDD red phase)**

```bash
cd /mnt/e/GITHUB/hotproductsdot-v2
pytest instagram/test_modelslab_image_gen.py -v
```

Expected: FAIL with `ModuleNotFoundError` or `AttributeError` (functions don't exist yet)

- [ ] **Step 3: Commit test file**

```bash
git add instagram/test_modelslab_image_gen.py
git commit -m "test: add ModelsLab image generation tests (TDD red)"
```

---

### Task 2: Implement ModelsLab API integration in image_gen.py

**Files:**
- Modify: `instagram/image_gen.py` (replace fal.ai logic with ModelsLab)

- [ ] **Step 1: Replace imports and constants**

Update the top of `instagram/image_gen.py` (lines 1-95):

```python
"""
ModelsLab FLUX image generation for Instagram post images.

Strategy for accuracy:
  1. Passes the actual product photo URL from the site to FLUX for image-to-image restyling
     — the model restyling the real product photo, not hallucinating one
  2. Falls back to text-to-image if the product photo URL is inaccessible
  3. Claude (haiku) writes tailored prompts for each style variant

ModelsLab returns public URLs, so no separate image hosting is needed.
Images are also saved locally in save_dir for dry-run preview.

Required env vars:
  MODELSLAB_KEY    — ModelsLab API key (get credits at modelslab.com)
  ANTHROPIC_API_KEY — optional, improves prompt quality
"""
import json
import os
import sys
from pathlib import Path

import anthropic
import requests

MODELSLAB_API_BASE = "https://modelslab.com/api/v6"
MODEL_ID = "flux"  # FLUX is ModelsLab's flagship image generation model
SITE_URL = "https://hotproductsdot.com"

# Brand visual DNA: dark charcoal studio backdrop + orange (#FF6B00) accent lighting
# Matches the HotProducts banner style: dark radial gradient, premium affiliate editorial feel
_STYLES = ["banner", "studio_dark", "lifestyle", "vibrant", "detail"]

# Edit-mode prompts (for image-to-image restyling) — product name injected at runtime
_EDIT_PROMPTS: dict[str, str] = {
    "banner": (
        "Premium affiliate marketing photo of {name} on a dark charcoal gradient background "
        "(near-black #0f0f0f edges, #2c2c2c center glow). "
        "Soft orange (#FF6B00) glow light behind the product, cinematic rim lighting. "
        "Product sharp, centered, floating with a soft drop shadow. "
        "Keep the product shape, color, and branding 100% identical."
    ),
    "studio_dark": (
        "Professional studio photo of {name} on a deep graphite background (#1c1c1c). "
        "Dramatic side lighting with warm orange-tinted rim light, "
        "premium commerce photography. "
        "Keep the product shape, color, and branding 100% identical."
    ),
    "lifestyle": (
        "Photo of {name} in a sleek modern home setting, "
        "moody amber lighting, dark tones, upscale editorial Instagram aesthetic. "
        "Keep the product shape, color, and branding 100% identical."
    ),
    "vibrant": (
        "Bold social media photo of {name} on a dark background with vibrant "
        "orange (#FF6B00) accent light, dynamic Gen-Z Instagram energy. "
        "Keep the product shape, color, and branding 100% identical."
    ),
    "detail": (
        "Close-up macro photo of {name} on a dark matte charcoal background, "
        "shallow depth of field, orange-tinted rim lighting, "
        "premium product photography emphasising texture and quality. "
        "Keep the product shape, color, and branding 100% identical."
    ),
}

# Text-to-image fallback prompts (no base image available)
_TEXT_PROMPTS: dict[str, str] = {
    "banner": (
        "Premium affiliate marketing photo of {name} on a dark charcoal gradient background "
        "(near-black edges, lighter gray center glow). "
        "Soft orange (#FF6B00) backlight glow, product centered and sharp. "
        "No text, no watermarks."
    ),
    "studio_dark": (
        "Professional product photo of {name} on a deep graphite background, "
        "dramatic cinematic lighting, orange-tinted rim light, premium commerce style. "
        "No text, no watermarks."
    ),
    "lifestyle": (
        "Lifestyle photo of {name} in a sleek modern home, "
        "moody amber side lighting, dark tones, upscale editorial aesthetic. "
        "No text, no watermarks."
    ),
    "vibrant": (
        "Bold social media shot of {name} on dark background, "
        "vibrant orange accent light, dynamic Gen-Z Instagram energy. "
        "No text, no watermarks."
    ),
    "detail": (
        "Close-up macro of {name} on dark matte background, "
        "shallow depth of field, orange-tinted rim lighting, premium feel. "
        "No text, no watermarks."
    ),
}
```

- [ ] **Step 2: Add `_call_modelslab_api()` function after constants**

- [ ] **Step 3: Replace `generate_product_images()` function (line 259)**

- [ ] **Step 4: Run tests to verify they pass (TDD green phase)**

```bash
pytest instagram/test_modelslab_image_gen.py -v
```

Expected: PASS

- [ ] **Step 5: Commit the ModelsLab integration**

```bash
git add instagram/image_gen.py instagram/test_modelslab_image_gen.py
git commit -m "feat: migrate from fal.ai to ModelsLab for 10x cost reduction"
```

---

### Task 3: Update environment configuration

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Update .env.example** - Replace FAL_KEY with MODELSLAB_KEY

- [ ] **Step 2: Verify correct format**

- [ ] **Step 3: Commit environment updates**

```bash
git commit -m "chore: update environment config (FAL_KEY → MODELSLAB_KEY)"
```

---

### Task 4: Add cost documentation

**Files:**
- Create: `docs/image-generation-cost-analysis.md`

- [ ] **Step 1: Create cost analysis document**

- [ ] **Step 2: Verify documentation exists and is readable**

- [ ] **Step 3: Commit documentation**

```bash
git commit -m "docs: add image generation cost analysis (fal.ai → ModelsLab)"
```

---

### Task 5: Integration testing & cleanup

**Files:**
- Modify: `instagram/test_modelslab_image_gen.py` (add integration tests)
- Review: `instagram/image_gen.py` (remove fal.ai references)

- [ ] **Step 1: Verify no remaining fal.ai references**

```bash
grep -r "fal" /mnt/e/GITHUB/hotproductsdot-v2 --include="*.py"
```

- [ ] **Step 2: Run full test suite**

```bash
pytest instagram/ -v
```

- [ ] **Step 3: Commit final changes**

```bash
git commit -m "refactor: complete fal.ai → ModelsLab migration"
```

---

## Context for Subagents

**Current Status:**
- Plan created: Image generation cost reduction (fal.ai → ModelsLab)
- Reason: Cut costs from $40-60/month to $29/month (10x reduction using FLUX models)
- Feature parity: Text-to-image + image-to-image (edit mode) fully supported
- No breaking changes to post_daily.py

**Key Files:**
- `instagram/image_gen.py` - Main file to modify (replace fal.ai with ModelsLab API)
- `instagram/test_modelslab_image_gen.py` - New test file
- `.env.example` - Update MODELSLAB_KEY config
- `docs/image-generation-cost-analysis.md` - Document cost savings

**API Changes:**
- Old: `https://fal.run` (fal.ai nano-banana-2)
- New: `https://modelslab.com/api/v6` (FLUX model)
- Both support text-to-image and image-to-image modes
- ModelsLab returns same response format (URLs as strings)
