import json

import httpx
from bs4 import BeautifulSoup

url = "https://www.adidas.com.tr/tr/adizero-aruku/JQ1616.html"
print(f"Fetching {url} with standard HTTP...")

resp = httpx.get(url, follow_redirects=True, timeout=15)
resp.raise_for_status()
print(f"Status Code: {resp.status_code}")
print(f"HTML Length: {len(resp.text)}")
print(f"HTML Content:\n{resp.text}\n")

soup = BeautifulSoup(resp.text, "html.parser")
json_lds = soup.find_all("script", type="application/ld+json")
print(f"Found {len(json_lds)} JSON-LD scripts.")

for i, script in enumerate(json_lds):
    if not script.string:
        continue
    try:
        data = json.loads(script.string)
        if isinstance(data, dict):
            if data.get("@type") == "ProductGroup":
                print("-> Found ProductGroup!")
                variants = data.get("hasVariant", [])
                print(f"-> Found {len(variants)} variants.")
    except (TypeError, ValueError, json.JSONDecodeError):
        continue
