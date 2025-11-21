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

# 4. Run the loader script (load_fit_to_es.py is now a standalone file in the repo)
# The script now supports configuration via:
# - CLI argument: --folder /path/to/fit/files
# - Environment variable: FIT_FOLDER=/path/to/fit/files
# - Default: ./garmin (relative to script location)
python load_fit_to_es.py

# 5. Access Kibana Dashboard
# Visit http://localhost:5601 and:
# - Go to "Stack Management > Index Patterns"
# - Create index pattern: fit-data*
# - Visualize metrics like heart_rate, cadence, speed etc. using "Visualize > Create Visualization"
# - New fields available: hr_drift_pct, normalized_power, training_stress_score, intensity_factor, moving_time_sec, avg_hr, avg_power, distance_m, elevation_gain_m, pause_time_sec

# Done!