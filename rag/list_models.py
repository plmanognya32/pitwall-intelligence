import os
import requests

GEMINI_AI_KEY = os.environ["GEMINI_AI_KEY"]

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_AI_KEY}"
resp = requests.get(url, timeout=15)
print(resp.status_code)
data = resp.json()

print("\n--- available embedding models ---")
for model in data.get("models", []):
    if "embed" in model["name"].lower():
        print(model["name"])
        print("  supported:", model.get("supportedGenerationMethods", []))

print("\n--- available generate models ---")
for model in data.get("models", []):
    if "gemini" in model["name"].lower() and "generateContent" in model.get("supportedGenerationMethods", []):
        print(model["name"])