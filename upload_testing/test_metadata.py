import json
import requests

# Load metadata
with open('metadata.json', 'r') as f:
    metadata = json.load(f)

# Upload it
response = requests.post('http://localhost:5007/upload_metadata', json=metadata)
print(f"Status: {response.status_code}")