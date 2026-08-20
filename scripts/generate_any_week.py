import sys
import os
import json
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.config import DATASET_PATH

def generate_week_payload(target_week="2026-W06"):
    import datetime
    try:
        parts = target_week.split('-W')
        year = int(parts[0])
        week_num = int(parts[1])
        iso_monday = datetime.date.fromisocalendar(year, week_num, 1).strftime('%Y-%m-%d')
    except Exception:
        year = 2026
        week_num = 5
        target_week = "2026-W05"
        iso_monday = "2026-01-26"

    df = pd.read_csv(DATASET_PATH).fillna({
        'trx': 0.0, 'nrx': 0.0, 'units': 0.0, 
        'brand': 'Unknown', 'product': 'Unknown', 
        'region': 'Tamil Nadu', 'therapeutic_area': 'Respiratory'
    })

    sample = df.sample(min(400, len(df)), random_state=week_num).copy()
    sample['date'] = iso_monday
    sample['week_number'] = week_num
    sample['year'] = year
    sample['year_week'] = target_week
    
    # Ensure numeric columns are floats without commas
    for col in ['trx', 'nrx', 'units']:
        sample[col] = sample[col].astype(str).str.replace(',', '').astype(float)

    records = sample[['date', 'week_number', 'year', 'region', 'therapeutic_area', 'product', 'brand', 'trx', 'nrx', 'units', 'year_week']].to_dict(orient='records')
    payload = {
        'year_week': target_week,
        'source_vendor': 'Central Market Data Feed',
        'records': records
    }

    out_file = os.path.join(os.path.dirname(__file__), "..", "sample_data", f"weekly_feed_{target_week.replace('-', '_')}_400_records.json")
    json.dump(payload, open(out_file, 'w'), indent=2)
    print(f"Successfully generated {len(records)} records for {target_week} in {out_file}")

if __name__ == "__main__":
    week_str = sys.argv[1] if len(sys.argv) > 1 else "2026-W06"
    generate_week_payload(week_str)
