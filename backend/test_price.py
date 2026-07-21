from pathlib import Path
import sys

import bs4


def main():
    if len(sys.argv) < 2:
        print("Usage: python backend/test_price.py <html-file>")
        return 0

    html_path = Path(sys.argv[1])
    if not html_path.exists():
        print(f"File not found: {html_path}")
        return 1

    soup = bs4.BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "lxml")
    for el in soup.find_all(string=lambda text: text and ("TL" in text or "?" in text)):
        parent = el.parent
        classes = parent.get("class", [])
        print(f"{parent.name} {classes}: {el.strip()[:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
