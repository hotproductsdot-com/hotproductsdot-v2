import unittest
from unittest.mock import patch, MagicMock
import os

from post_daily import post_instagram

class TestPostInstagram(unittest.TestCase):
    @patch("post_daily.requests.post")
    def test_post_instagram_success(self, mock_post):
        # Setup mock environment
        os.environ["IG_USER_ID"] = "12345"
        os.environ["IG_ACCESS_TOKEN"] = "token123"
        
        # Mock responses for the two steps
        mock_resp1 = MagicMock()
        mock_resp1.json.return_value = {"id": "media999"}
        
        mock_resp2 = MagicMock()
        mock_resp2.json.return_value = {"id": "post777"}
        
        mock_post.side_effect = [mock_resp1, mock_resp2]
        
        product = {
            "name": "Test Product",
            "slug": "test-product",
            "category": "Gadgets",
            "price": "99.99",
            "rating": 4.5,
            "reviews": "100",
            "potential": 8
        }
        
        result = post_instagram(product)
        
        self.assertTrue(result["ok"])
        self.assertEqual(result["post_id"], "post777")
        self.assertEqual(result["platform"], "instagram")
        
        # Verify first call (media creation) used 'data' properly
        self.assertEqual(mock_post.call_count, 2)
        args, kwargs = mock_post.call_args_list[0]
        self.assertIn("12345/media", args[0])
        self.assertIn("data", kwargs)
        self.assertEqual(kwargs["data"]["access_token"], "token123")
        self.assertIn("image_url", kwargs["data"])
        self.assertIn("caption", kwargs["data"])
        
        # Verify second call (publish)
        args, kwargs = mock_post.call_args_list[1]
        self.assertIn("12345/media_publish", args[0])
        self.assertIn("data", kwargs)
        self.assertEqual(kwargs["data"]["creation_id"], "media999")
        self.assertEqual(kwargs["data"]["access_token"], "token123")

if __name__ == "__main__":
    unittest.main()
