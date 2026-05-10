"""Investigation: ping Cloudinary with the .env CLOUDINARY_URL to see the
exact failure reason post_daily is hitting."""
import os
import sys

sys.path.insert(0, "/mnt/e/GITHUB/hotproductsdot-v2")
os.chdir("/mnt/e/GITHUB/hotproductsdot-v2")

from dotenv import load_dotenv

load_dotenv(override=True)

from instagram import banner_compose

url = os.environ.get("CLOUDINARY_URL", "")
print(f"CLOUDINARY_URL set: {bool(url)} (len={len(url)})")
parsed = banner_compose._parse_cloudinary_url(url) if url else None
print(f"parsed: {bool(parsed)}")
if not parsed:
    sys.exit(1)
cloud, key, secret = parsed
print(f"cloud_name={cloud!r} api_key_len={len(key)} secret_len={len(secret)}")

# Try uploading any existing local banner.
import glob

candidates = glob.glob(
    "/mnt/e/GITHUB/hotproductsdot-v2/generated_images/*/*/banner.jpg"
)
if not candidates:
    print("no local banner.jpg found to upload")
    sys.exit(2)
test_file = candidates[0]
print(f"uploading {test_file}")
result = banner_compose.upload_to_cloudinary(
    test_file, url, public_id="hotproducts/_diag-test"
)
print(f"result: {result!r}")
