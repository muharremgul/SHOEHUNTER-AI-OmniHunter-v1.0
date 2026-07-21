import json
import sys

def get_message():
    path = r"C:\Users\ÖGR1\.gemini\antigravity\brain\51c1b3e8-5823-4507-b391-befd670bad54\.system_generated\logs\transcript.jsonl"
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == 563:
                data = json.loads(line)
                print(data.get("content").encode("cp1254", errors="ignore").decode("cp1254"))
                break

if __name__ == "__main__":
    get_message()
