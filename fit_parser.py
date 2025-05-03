import pandas as pd
from fitparse import FitFile
import json
import os
import zipfile
import requests
import argparse
import concurrent.futures
from tqdm import tqdm
from tkinter import Tk, filedialog
from datetime import datetime
from zones import get_heart_rate_zone, get_power_zone

ELASTIC_URL = 'http://localhost:9200/cycling-data/_doc'

def parse_fit_file(file_path):
    fitfile = FitFile(file_path)
    records = []
    for record in fitfile.get_messages('record'):
        record_data = {}
        for data in record:
            record_data[data.name] = data.value
        records.append(record_data)
    df = pd.DataFrame(records)
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df.dropna(how='all', inplace=True)
    return df

def post_doc(doc, elastic_url, session):
    headers = {'Content-Type': 'application/json'}
    try:
        res = session.post(elastic_url, headers=headers, data=json.dumps(doc))
        if res.status_code not in [200, 201]:
            return f"Failed POST: {res.status_code} {res.text}"
    except requests.exceptions.RequestException as e:
        return f"Request error: {e}"
    return None  # success

def process_file(file_path, args, session):
    log = {'file': file_path, 'records': 0, 'errors': []}
    try:
        df = parse_fit_file(file_path)
        if df.empty:
            log['errors'].append("No data")
            return log

        # Convert timestamp column to ISO string
        if 'timestamp' in df.columns:
            df['timestamp'] = df['timestamp'].apply(lambda x: x.isoformat() if pd.notnull(x) else None)
            
        if 'heart_rate' in df.columns:
            df['heart_rate_zone'] = df['heart_rate'].apply(get_heart_rate_zone)

        if 'power' in df.columns:
            df['power_zone'] = df['power'].apply(get_power_zone)

        output_path = os.path.splitext(file_path)[0] + '.json'
        df.to_json(output_path, orient='records', lines=True)
        log['records'] = len(df)

        if args.post:
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(post_doc, row.to_dict(), ELASTIC_URL, session) for _, row in df.iterrows()]
                for future in concurrent.futures.as_completed(futures):
                    error = future.result()
                    if error:
                        log['errors'].append(error)

        return log
    except Exception as e:
        log['errors'].append(f"Processing error: {e}")
        return log

def main():
    parser = argparse.ArgumentParser(description="Batch FIT Parser + Elasticsearch Uploader")
    parser.add_argument('--no-post', action='store_true', help="Skip Elasticsearch POST")
    parser.add_argument('--only-zip', action='store_true', help="Only zip JSONs, skip parse + post")
    args = parser.parse_args()
    args.post = not args.no_post

    fit_dir = 'fit_files/sample'
    file_paths = [os.path.join(fit_dir, f) for f in os.listdir(fit_dir) if f.endswith('.fit')]

    if not file_paths:
        print("No .fit files found in folder.")
        return

    json_files, logs = [], []
    with requests.Session() as session:
        for file_path in tqdm(file_paths, desc="Processing files"):
            log = process_file(file_path, args, session)
            logs.append(log)
            json_path = os.path.splitext(file_path)[0] + '.json'
            if os.path.exists(json_path):
                json_files.append(json_path)

    # Zip JSON files
    if json_files:
        zip_path = os.path.join('fit_files', 'all_activities.zip')
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for json_file in json_files:
                zipf.write(json_file, arcname=os.path.basename(json_file))
        print(f"\nZipped all JSONs into {zip_path}")

    # Save log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = f'process_log_{timestamp}.txt'
    with open(log_path, 'w') as f:
        for log in logs:
            f.write(f"File: {log['file']}\nRecords: {log['records']}\n")
            if log['errors']:
                f.write("Errors:\n")
                for err in log['errors']:
                    f.write(f"  - {err}\n")
            f.write("\n")
    print(f"\nSaved log to {log_path}")
    print("\n? All done!")

if __name__ == "__main__":
    main()
