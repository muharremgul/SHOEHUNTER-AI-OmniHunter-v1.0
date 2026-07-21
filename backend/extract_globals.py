import re

def analyze():
    with open("intersport_test.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    matches = re.finditer(r"var\s+GLOBALS\s*=\s*(\{.*?\});", html, re.DOTALL)
    for m in matches:
        print(m.group(1)[:1000])

if __name__ == "__main__":
    analyze()
