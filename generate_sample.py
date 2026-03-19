import base64
import json
import os

img_path = r"d:\ATMOSCHAIN\datasets\waste_images_dataset\test\plastic\plastic_00001.jpg"
out_path = r"d:\ATMOSCHAIN\sample_payload.json"

if not os.path.exists(img_path):
    print(f"Error: Could not find image at {img_path}")
else:
    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")
    
    payload = {
        "image_b64": img_b64,
        "mass_override_kg": 0.5
    }
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    
    print(f"Successfully created: {out_path}")
