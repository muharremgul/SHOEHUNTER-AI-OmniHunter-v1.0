import bs4
with open(r'C:\Users\ÖGR1\Documents\Ayakkabi\gecici\adidas Adizero Aruku Ayakkabý - Beyaz _ adidas Türkiye.html', 'r', encoding='utf-8') as f:
    soup = bs4.BeautifulSoup(f.read(), 'lxml')
for el in soup.find_all(string=lambda text: text and ('TL' in text or '?' in text)):
    p = el.parent
    c = p.get('class', [])
    print(f"{p.name} {c}: {el.strip()[:100]}")
