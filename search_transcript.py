import json
import sys

def search_transcript():
    path = r"C:\Users\ÖGR1\.gemini\antigravity\brain\51c1b3e8-5823-4507-b391-befd670bad54\.system_generated\logs\transcript.jsonl"
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            try:
                data = json.loads(line)
                if data.get("type") == "PLANNER_RESPONSE":
                    content = data.get("content", "").lower()
                    if "stok" in content and "planı kodladım" in content:
                        print(f"Match 1 (Line {i}): {data.get('content')[:500]}...")
                    if "stok" in content and "çözüldü" in content and "intersport" in content:
                        print(f"Match 2 (Line {i}): {data.get('content')[:500]}...")
            except Exception:
                pass

if __name__ == "__main__":
    search_transcript()
