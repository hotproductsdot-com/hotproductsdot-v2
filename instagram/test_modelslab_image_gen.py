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
