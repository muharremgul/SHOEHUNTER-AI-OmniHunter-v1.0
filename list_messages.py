import json

def list_messages():
    path = r"C:\Users\ÖGR1\.gemini\antigravity\brain\51c1b3e8-5823-4507-b391-befd670bad54\.system_generated\logs\transcript.jsonl"
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            try:
                data = json.loads(line)
                if data.get("type") == "PLANNER_RESPONSE":
                    content = data.get("content", "")
                    # Ignore thought blocks inside responses if any
                    if "Critical instructions 1 and 2" not in content[:50]:
                        print(f"Line {i}: {content[:100]}...")
            except Exception:
                pass

if __name__ == "__main__":
    list_messages()
