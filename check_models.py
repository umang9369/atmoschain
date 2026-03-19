import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv("d:\\ATMOSCHAIN\\.env")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

print("=== Available Vision & Flash Models for this Key ===")
try:
    for m in genai.list_models():
        if "generateContent" in m.supported_generation_methods:
            name = m.name.lower()
            if "flash" in name or "pro" in name or "gemini" in name:
                print(m.name)
except Exception as e:
    print(f"Error listing models: {e}")
