import urllib.request
import urllib.error
import json
import base64
import os

# 1. Path to one of the synthetic test images we generated earlier
image_path = r"datasets\waste_images_dataset\train\plastic\plastic_001.jpg"

# 2. Read the image and encode it to base64
with open(image_path, "rb") as image_file:
    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

# 3. Construct the exact payload format the API expects
payload = {
    "image_b64": encoded_string,
    "mass_override_kg": 0.5  # Testing with 500 grams
}

# 4. Define the Exact API Endpoint URL (as defined in wastevision_routes.py)
url = "http://127.0.0.1:8000/api/detect"

# 5. Send the POST request
req = urllib.request.Request(
    url, 
    data=json.dumps(payload).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)

print(f"Sending POST request to {url}...")
try:
    with urllib.request.urlopen(req) as response:
        result = response.read().decode('utf-8')
        print("\n=== API RESPONSE SUCCESS ===")
        
        # Pretty print the JSON response
        parsed_json = json.loads(result)
        print(json.dumps(parsed_json, indent=2))
        
except urllib.error.HTTPError as e:
    print(f"\nAPI HTTP ERROR: {e.code} - {e.reason}")
    print(e.read().decode('utf-8'))
except urllib.error.URLError as e:
    print(f"\nSERVER CONNECTION ERROR: {e.reason}")
    print("Is the uvicorn server running on port 8000?")
