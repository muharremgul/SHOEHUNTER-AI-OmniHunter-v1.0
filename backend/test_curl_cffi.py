from curl_cffi import requests
from bs4 import BeautifulSoup
import json

url = "https://www.adidas.com.tr/tr/adizero-aruku/JQ1616.html"
print(f"Fetching {url} with curl_cffi...")

resp = requests.get(url, impersonate="chrome110", timeout=15)
print(f"Status Code: {resp.status_code}")
print(f"HTML Length: {len(resp.text)}")
print(f"HTML Content:\n{resp.text}\n")

soup = BeautifulSoup(resp.text, "html.parser")
json_lds = soup.find_all("script", type="application/ld+json")
print(f"Found {len(json_lds)} JSON-LD scripts.")

for i, script in enumerate(json_lds):
    if not script.string: continue
    try:
        data = json.loads(script.string)
        if isinstance(data, dict):
            if data.get('@type') == 'ProductGroup':
                print("-> Found ProductGroup!")
                variants = data.get('hasVariant', [])
                print(f"-> Found {len(variants)} variants.")
    except Exception as e:
        pass
