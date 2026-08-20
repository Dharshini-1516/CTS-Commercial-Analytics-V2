import sys
import os
import json
import requests

def ingest_week(target_week="2026-W05", api_url="http://localhost:8000"):
    parts = target_week.replace('-', '_')
    json_path = os.path.join(os.path.dirname(__file__), "..", "sample_data", f"weekly_feed_{parts}_400_records.json")
    
    if not os.path.exists(json_path):
        print(f"File {json_path} not found. Generating...")
        os.system(f"python {os.path.join(os.path.dirname(__file__), 'generate_any_week.py')} {target_week}")

    if os.path.exists(json_path):
        payload = json.load(open(json_path, 'r'))
        target_endpoint = f"{api_url.rstrip('/')}/api/v1/ingest-weekly-data"
        print(f"Sending {len(payload['records'])} records for {target_week} to {target_endpoint}...")
        try:
            res = requests.post(target_endpoint, json=payload, timeout=30)
            print(f"Status Code: {res.status_code}")
            print(f"Response: {json.dumps(res.json(), indent=2)}")
        except Exception as e:
            print(f"Ingestion failed: {e}")
    else:
        print(f"Could not locate payload for {target_week}")

if __name__ == "__main__":
    week = sys.argv[1] if len(sys.argv) > 1 else "2026-W05"
    url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"
    ingest_week(week, url)
