import json
import requests

# Load metadata
with open('metadata.json', 'r') as f:
    metadata = json.load(f)

# Upload it
# response = requests.post('https://qc.allenneuraldynamics-test.org/upload_metadata', json=metadata)
response = requests.post('http://localhost:5007/upload_metadata', json=metadata)

# Name: multiplane-ophys_692478_2023-09-29_08-53-45_processed_2025-04-22_20-50-47

print(f"Status: {response.status_code}")
