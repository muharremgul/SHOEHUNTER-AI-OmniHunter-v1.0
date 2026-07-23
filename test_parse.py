from bs4 import BeautifulSoup

html = open("gs_vomero_curl.html", encoding="utf-8").read()
soup = BeautifulSoup(html, "html.parser")

cards = soup.select(".sh-dgr__content, .sh-dgr__grid-result, .i0X6df, div[data-docid]")
print("Original selector found:", len(cards))

# Let's find ANY link that has 'vomero'
for a in soup.find_all("a"):
    text = a.get_text(strip=True).lower()
    if "vomero" in text and len(text) > 10:
        print("Found link:", text)
        print("  Classes:", a.get("class"))
        parent = a.parent
        print("  Parent classes:", parent.name, parent.get("class"))
        print("  Has price?", any("₺" in s for s in parent.strings))
        print("---")
