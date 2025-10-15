import os
import json
import datetime
from fitparse import FitFile
from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk
from tqdm import tqdm

# Configuration
FOLDER = "garmin"  # Relative path to garmin folder
FTP = 210  # Update with your current FTP value
es = Elasticsearch("http://localhost:9200")
INDEX = "fit-data"

HR_ZONES = {
    "heart_rate_zone_1": (98, 117),
    "hrz2": (118, 137),
    "hrz3": (138, 156),
    "hrz4": (157, 176),
    "hrz5": (177, 195),
}

POWER_ZONES = {
    "power_zone_1": (0, 109),
    "pwz2": (110, 149),
    "pwz3": (150, 179),
    "pwz4": (180, 210),
    "pwz5": (211, 239),
    "pwz6": (240, 298),
    "pwz7": (299, float("inf")),
}

def classify_zone(value, zones):
    if value is None:
        return None
    for name, (low, high) in zones.items():
        if low <= value <= high:
            return name
    return None

def compute_session_metrics(records):
    powers = [r.get("power") for r in records if isinstance(r.get("power"), (int, float))]
    hrs = [r.get("heart_rate") for r in records if isinstance(r.get("heart_rate"), (int, float))]
    timestamps = [r.get("timestamp") for r in records if isinstance(r.get("timestamp"), datetime.datetime)]
    elevations = [r.get("altitude") for r in records if isinstance(r.get("altitude"), (int, float))]
    distances = [r.get("distance") for r in records if isinstance(r.get("distance"), (int, float))]

    moving_time = len(powers)
    pause_time = sum([max((timestamps[i+1] - timestamps[i]).total_seconds() - 1, 0) for i in range(len(timestamps)-1)])

    avg_power = sum(powers)/len(powers) if powers else 0
    avg_hr = sum(hrs)/len(hrs) if hrs else 0
    normalized_power = (sum([p**4 for p in powers]) / len(powers))**0.25 if powers else 0
    intensity_factor = normalized_power / FTP if FTP > 0 else 0
    tss = (moving_time * normalized_power * intensity_factor) / (FTP * 3600) * 100 if FTP > 0 else 0

    midpoint = len(records) // 2
    drift = None
    if midpoint > 0:
        p1 = [r.get("power") for r in records[:midpoint] if isinstance(r.get("power"), (int, float))]
        h1 = [r.get("heart_rate") for r in records[:midpoint] if isinstance(r.get("heart_rate"), (int, float))]
        p2 = [r.get("power") for r in records[midpoint:] if isinstance(r.get("power"), (int, float))]
        h2 = [r.get("heart_rate") for r in records[midpoint:] if isinstance(r.get("heart_rate"), (int, float))]
        if p1 and p2 and h1 and h2:
            hr_1 = sum(h1) / len(h1)
            pw_1 = sum(p1) / len(p1)
            hr_2 = sum(h2) / len(h2)
            pw_2 = sum(p2) / len(p2)
            if pw_1 > 0:
                drift = ((hr_2 / pw_2) - (hr_1 / pw_1)) / (hr_1 / pw_1) * 100

    return {
        "avg_power": avg_power,
        "avg_hr": avg_hr,
        "moving_time_sec": moving_time,
        "pause_time_sec": pause_time,
        "distance_m": max(distances) if distances else None,
        "elevation_gain_m": max(elevations) - min(elevations) if elevations else None,
        "normalized_power": normalized_power,
        "intensity_factor": intensity_factor,
        "training_stress_score": tss,
        "hr_drift_pct": drift,
    }

def parse_fit_file(path):
    print(f"Parsing {path}...")
    fitfile = FitFile(path)
    data = []
    for record in fitfile.get_messages("record"):
        fields = {f.name: f.value for f in record}
        fields["heart_rate_zone"] = classify_zone(fields.get("heart_rate"), HR_ZONES)
        fields["power_zone"] = classify_zone(fields.get("power"), POWER_ZONES)
        data.append(fields)
    return data

def load_to_es():
    # Get list of .fit files
    files = [f for f in os.listdir(FOLDER) if f.endswith(".fit")]
    total_records = 0
    
    print(f"\nFound {len(files)} .fit files to process\n")
    
    # Process each file with progress bar
    for file in tqdm(files, desc="Processing files", unit="file", position=0):
        file_path = os.path.join(FOLDER, file)
        records = parse_fit_file(file_path)
        session_metrics = compute_session_metrics(records)
        session_id = os.path.splitext(file)[0]
        
        # Prepare bulk actions
        actions = []
        for record in records:
            record["session_id"] = session_id
            record.update(session_metrics)
            actions.append({
                "_index": INDEX,
                "_source": record
            })
        
        # Bulk index with progress
        success_count = 0
        error_count = 0
        
        for ok, response in streaming_bulk(
            es, 
            actions, 
            chunk_size=500,
            raise_on_error=False
        ):
            if ok:
                success_count += 1
            else:
                error_count += 1
        
        total_records += success_count
        
        if error_count > 0:
            tqdm.write(f"  WARNING: {file}: {success_count} indexed, {error_count} errors")
    
    print(f"\nSUCCESS: Indexed {total_records} records from {len(files)} files")

if __name__ == "__main__":
    print("Connecting to Elasticsearch...")
    print("Deleting existing index (if any)...")
    es.indices.delete(index=INDEX, ignore_unavailable=True)
    print("Creating new index...")
    es.indices.create(index=INDEX, ignore=400)
    print("\nLoading .fit files from 'garmin' folder...")
    load_to_es()
    print("\nDone! Visit http://localhost:5601 to view in Kibana")

