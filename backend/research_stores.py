import os
from curl_cffi import requests

URLS = {
    "nike": "https://www.nike.com.tr/urun/air-force-1-07-erkek-ayakkabisi-j4K2L7", 
    "puma": "https://tr.puma.com/tr/tr/pd/suede-classic-xxi-erkek-spor-ayakkabi/374915_01.html",
    "newbalance": "https://www.newbalance.com.tr/bb550ncg-bb550ncg-40618"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

for name, url in URLS.items():
    print(f"Fetching {name}...")
    try:
        resp = requests.get(url, impersonate="chrome110", timeout=15)
        print(f"[{name}] Status: {resp.status_code}, Length: {len(resp.text)}")
        
        with open(f"scratch_{name}.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
    except Exception as e:
        print(f"Error fetching {name}: {e}")
