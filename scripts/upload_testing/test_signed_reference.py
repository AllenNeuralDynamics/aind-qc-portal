"""Test the /get-signed-reference endpoint on a running QC portal server"""

import sys
from urllib.parse import urlencode

import requests

ASSET_NAME = "ecephys_838101_2026-04-29_15-20-10_sorted-curation-sprint_2026-05-12_17-45-28"
REFERENCE = "quality_control/experiment1_ProbeA_group0/traces_raw.png"
BASE_URL = "http://localhost:5007"

params = urlencode({"reference": REFERENCE})
url = f"{BASE_URL}/get-signed-reference/{ASSET_NAME}?{params}"

print(f"GET {url}")
response = requests.get(url)
print(f"Status: {response.status_code}")

if response.ok:
    print(f"Signed URL: {response.json()['url']}")
else:
    print(f"Error: {response.text}")
    sys.exit(1)