from pathlib import Path

import httpx

URLS = {
    "nike": "https://www.nike.com.tr/urun/air-force-1-07-erkek-ayakkabisi-j4K2L7",
    "puma": "https://tr.puma.com/tr/tr/pd/suede-classic-xxi-erkek-spor-ayakkabi/374915_01.html",
    "newbalance": "https://www.newbalance.com.tr/bb550ncg-bb550ncg-40618",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def main():
    with httpx.Client(headers=HEADERS, timeout=15, follow_redirects=True) as client:
        for name, url in URLS.items():
            print(f"Fetching {name}...")
            try:
                response = client.get(url)
                response.raise_for_status()
                print(f"[{name}] Status: {response.status_code}, Length: {len(response.text)}")
                Path(f"scratch_{name}.html").write_text(response.text, encoding="utf-8")
            except httpx.HTTPError as exc:
                print(f"Error fetching {name}: {exc}")


if __name__ == "__main__":
    main()
