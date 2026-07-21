import json

def get_messages():
    path = r"C:\Users\ÖGR1\.gemini\antigravity\brain\51c1b3e8-5823-4507-b391-befd670bad54\.system_generated\logs\transcript.jsonl"
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if 500 < i < 600:
                try:
                    data = json.loads(line)
                    if data.get("type") == "PLANNER_RESPONSE":
                        content = data.get("content", "")
                        print(f"Line {i}: {content[-200:]}") # Print the END of the message to avoid thoughts
                except Exception:
                    pass

if __name__ == "__main__":
    get_messages()
