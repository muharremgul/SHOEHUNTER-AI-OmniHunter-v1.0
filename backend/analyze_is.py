import sys
import os
import re

def analyze_file(filename):
    print(f"\n--- Analyzing {filename} ---")
    with open(filename, "r", encoding="utf-8") as f:
        html = f.read()
    
    # Check for "is_sellable", "in_stock", "quantity", "stock" in any JS blocks
    matches = re.finditer(r'<script.*?>.*?(is_sellable|in_stock|quantity|stock|"sizes"|"variants"|product).*?</script>', html, re.DOTALL | re.IGNORECASE)
    
    for m in matches:
        text = m.group(0)
        if len(text) > 2000:
            text = text[:1000] + "...[truncated]..." + text[-1000:]
        print(f"Found match: {text[:500]}")

if __name__ == "__main__":
    analyze_file("is0.html")
    analyze_file("is1.html")
    analyze_file("is2.html")
