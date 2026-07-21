from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

def main():
    print("Sending /api/search request...")
    response = client.post("/api/search", json={"query": "brooks 23", "use_ai": False})
    print("Status:", response.status_code)
    try:
        data = response.json()
        print("Total results:", data.get("total_results"))
        for s in data.get("stores", []):
            print(f"{s['store']}: {s['status']} - {len(s.get('results', []))} results")
            if s.get('error'):
                print("  Error:", s['error'])
    except Exception as e:
        print("Failed to parse JSON:", e)
        print(response.text[:500])

if __name__ == "__main__":
    main()
