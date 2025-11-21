# Step-by-step ELK Stack + Garmin .fit Analysis Setup on Mac

# 1. Install Docker Desktop for Mac (if not already installed)
# Visit https://www.docker.com/products/docker-desktop and follow installation instructions

# 2. Pull and Run ELK Stack using Docker
mkdir -p ~/elk-stack && cd ~/elk-stack

# Create a Docker Compose file for ELK
cat <<EOF > docker-compose.yml
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.13.4
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - xpack.monitoring.collection.enabled=true
    ports:
      - "9200:9200"
      - "9300:9300"
    volumes:
      - esdata:/usr/share/elasticsearch/data

  kibana:
    image: docker.elastic.co/kibana/kibana:8.13.4
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200

volumes:
  esdata:
EOF

# Start ELK Stack
open http://localhost:5601 # Optional - open Kibana interface

docker compose up -d

# 3. Set up Python environment to convert .fit to .json
python3 -m venv elk_env
source elk_env/bin/activate
pip install fitparse "elasticsearch<9"

# 4. Python script to convert and ingest
cat <<EOF > load_fit_to_es.py
import os
import json
import datetime
from fitparse import FitFile
from elasticsearch import Elasticsearch
import pandas as pd

hr_df = pd.read_csv("daily_hr_summary.csv", parse_dates=["date"])
hr_df["date"] = hr_df["date"].dt.date
hr_lookup = hr_df.set_index("date").to_dict(orient="index")

FOLDER = "/Users/personal/Desktop/private/fit/garmin"
FTP = 210  # Update with your current FTP value
es = Elasticsearch("http://localhost:9200")
INDEX = "fit-data"

HR_ZONES = {
    "hrz1": (98, 117),
    "hrz2": (118, 137),
    "hrz3": (138, 156),
    "hrz4": (157, 176),
    "hrz5": (177, 198),
}

POWER_ZONES = {
    "pwz1": (0, 109),
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

def get_max_5min_power(records):
    power_values = [r.get("power") for r in records if isinstance(r.get("power"), (int, float))]
    if len(power_values) < 300:
        return None  # not enough data for a 5-min interval
    s = pd.Series(power_values)
    rolling_avg = s.rolling(window=300).mean()
    return round(rolling_avg.max(), 1)

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
    max_5min_power = get_max_5min_power(records)
    vo2max_estimate = (max_5min_power * 12) / 73 if max_5min_power else None

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
        "max_5min_power": max_5min_power,
        "vo2max_estimate": round(vo2max_estimate, 1) if vo2max_estimate else None,
    }

def load_to_es():
    for file in os.listdir(FOLDER):
        if file.endswith(".fit"):
            records = parse_fit_file(os.path.join(FOLDER, file))
            session_metrics = compute_session_metrics(records)
            session_id = os.path.splitext(file)[0]
            
            # Extract session date for enrichment
            session_date = records[0].get("timestamp").date() if records and "timestamp" in records[0] else None
            enrichment = hr_lookup.get(session_date, {}) if session_date else {}

            for i, record in enumerate(records):
                record["session_id"] = session_id
                record.update(session_metrics)

                # Add Apple HR enrichment
                record.update({
                    "resting_hr": enrichment.get("resting_hr_avg"),
                    "min_hr": enrichment.get("min_hr"),
                    "hrv_avg": enrichment.get("hrv_avg"),
                })

                es.index(index=INDEX, id=f"{file}-{i}", document=record)

if __name__ == "__main__":
    es.indices.delete(index=INDEX, ignore_unavailable=True)
    es.indices.create(index=INDEX, ignore=400)
    load_to_es()
EOF

# 4A. Preprocess Apple Health HR data
cat <<EOF > parse_apple_hr.py
import xml.etree.ElementTree as ET
import pandas as pd
from collections import defaultdict

tree = ET.parse("apple_health_export/export.xml")
root = tree.getroot()

daily_hr_summary = defaultdict(lambda: {"resting_hr": [], "low_hr": [], "hrv": []})

for record in root.findall("Record"):
    record_type = record.attrib.get("type")
    start_date = record.attrib.get("startDate")
    value = record.attrib.get("value")

    if record_type in [
        "HKQuantityTypeIdentifierRestingHeartRate",
        "HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
        "HKQuantityTypeIdentifierHeartRate"
    ]:
        try:
            date = pd.to_datetime(start_date).date()
            val = float(value)
            if record_type == "HKQuantityTypeIdentifierRestingHeartRate":
                daily_hr_summary[date]["resting_hr"].append(val)
            elif record_type == "HKQuantityTypeIdentifierHeartRate":
                daily_hr_summary[date]["low_hr"].append(val)
            elif record_type == "HKQuantityTypeIdentifierHeartRateVariabilitySDNN":
                daily_hr_summary[date]["hrv"].append(val)
        except:
            continue

summary = []
for date, values in daily_hr_summary.items():
    resting_avg = round(pd.Series(values["resting_hr"]).mean(), 1) if values["resting_hr"] else None
    min_hr = round(pd.Series(values["low_hr"]).min(), 1) if values["low_hr"] else None
    hrv_avg = round(pd.Series(values["hrv"]).mean(), 1) if values["hrv"] else None
    summary.append({"date": date, "resting_hr_avg": resting_avg, "min_hr": min_hr, "hrv_avg": hrv_avg})

df = pd.DataFrame(summary)
df.sort_values(by="date", ascending=True, inplace=True)
df.to_csv("daily_hr_summary.csv", index=False)
EOF

# Run the HR parsing script
python parse_apple_hr.py

# Run the loader script
python load_fit_to_es.py

# 5. Access Kibana Dashboard
# Visit http://localhost:5601 and:
# - Go to "Stack Management > Index Patterns"
# - Create index pattern: fit-data*
# - Visualize metrics like heart_rate, cadence, speed etc. using "Visualize > Create Visualization"
# - New fields available: hr_drift_pct, normalized_power, training_stress_score, intensity_factor, moving_time_sec, avg_hr, avg_power, distance_m, elevation_gain_m, pause_time_sec

# Done!