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

FOLDER = "/Users/personal/Desktop/private/fit/garmin"
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
    fitfile = FitFile(path)
    data = []
    for record in fitfile.get_messages("record"):
        fields = {f.name: f.value for f in record}
        fields["heart_rate_zone"] = classify_zone(fields.get("heart_rate"), HR_ZONES)
        fields["power_zone"] = classify_zone(fields.get("power"), POWER_ZONES)
        data.append(fields)
    return data

def load_to_es():
    for file in os.listdir(FOLDER):
        if file.endswith(".fit"):
            records = parse_fit_file(os.path.join(FOLDER, file))
            session_metrics = compute_session_metrics(records)
            session_id = os.path.splitext(file)[0]
            for i, record in enumerate(records):
                record["session_id"] = session_id
                record.update(session_metrics)
                es.index(index=INDEX, id=f"{file}-{i}", document=record)

if __name__ == "__main__":
    es.indices.delete(index=INDEX, ignore_unavailable=True)
    es.indices.create(index=INDEX, ignore=400)
    load_to_es()
EOF

# Run the loader script
python load_fit_to_es.py

# 5. Access Kibana Dashboard
# Visit http://localhost:5601 and:
# - Go to "Stack Management > Index Patterns"
# - Create index pattern: fit-data*
# - Visualize metrics like heart_rate, cadence, speed etc. using "Visualize > Create Visualization"
# - New fields available: hr_drift_pct, normalized_power, training_stress_score, intensity_factor, moving_time_sec, avg_hr, avg_power, distance_m, elevation_gain_m, pause_time_sec

# Done!