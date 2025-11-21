# Garmin .fit → ELK Loader

This repository contains helper scripts to parse Apple Health export data and Garmin `.fit` files, convert them into records, and load them into an Elasticsearch instance (ELK stack) for visualization in Kibana.

The main entrypoint is `elk_fit_setup.sh`, a shell script that scaffolds a local ELK stack (via Docker Compose), creates two Python scripts (`parse_apple_hr.py` and `load_fit_to_es.py`), creates and activates a Python virtual environment, installs dependencies, runs the parsers, and loads parsed data into Elasticsearch.

## Prerequisites

- macOS (tested locally)
- Docker Desktop running (https://www.docker.com/products/docker-desktop)
- Python 3.8+ (system Python 3 is fine)
- Terminal (zsh / bash)

Optional:
- An Apple Health export folder at `apple_health_export/export.xml` if you want to enrich Garmin sessions with daily HR summaries.
- Your Garmin `.fit` files in the `garmin/` subfolder (this repo already includes sample `.fit` files).

## Quick run (one command)

Open a terminal in the repository root and run:

```sh
bash elk_fit_setup.sh
```

This will:
- Create `~/elk-stack/docker-compose.yml` and start Elasticsearch and Kibana via Docker Compose.
- Create a Python virtual environment `elk_env`, activate it, and install required packages (`fitparse`, `elasticsearch<9`, and `pandas`).
- Generate `parse_apple_hr.py` and `load_fit_to_es.py` scripts in the repo (these are already present in the repo as well).
- Run `parse_apple_hr.py` to produce `daily_hr_summary.csv` (requires `apple_health_export/export.xml`).
- Run `load_fit_to_es.py` which reads `.fit` files from the `garmin/` folder and indexes records into Elasticsearch index `fit-data`.

Note: `elk_fit_setup.sh` assumes Docker is running and `python3` is available on your PATH.

## Step-by-step manual run (recommended for debugging)

1. Start Docker Desktop and ensure it's running.
2. Create and start the ELK stack (from repo root or any directory):

```sh
mkdir -p ~/elk-stack && cd ~/elk-stack
cat > docker-compose.yml <<'EOF'
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

docker compose up -d
```

3. Wait for Elasticsearch to be ready (it may take a minute or two). You can check readiness with:

```sh
curl -sS http://localhost:9200/ | jq
```

If you don't have `jq`, a plain `curl http://localhost:9200` will also show a JSON response.

4. In the repo root create and activate a Python virtualenv:

```sh
python3 -m venv elk_env
source elk_env/bin/activate
pip install --upgrade pip
pip install fitparse "elasticsearch<9" pandas
```

5. Prepare Apple Health export (optional but recommended):

- Put your Apple Health export folder at `apple_health_export/` so `apple_health_export/export.xml` exists.
- Run the parser:

```sh
python parse_apple_hr.py
```

This writes `daily_hr_summary.csv` used to enrich sessions.

6. Run the FIT loader (it reads `.fit` files from `garmin/`):

```sh
python load_fit_to_es.py
```

The script will create the Elasticsearch index `fit-data` and index documents for each record. You can confirm by visiting Kibana at `http://localhost:5601`.

**Configuring the folder location:**

The script supports multiple ways to specify the folder containing `.fit` files (in order of precedence):

1. CLI argument: `python load_fit_to_es.py --folder /path/to/fit/files`
2. Environment variable: `FIT_FOLDER=/path/to/fit/files python load_fit_to_es.py`
3. Default: `./garmin` (relative to the script location)

## Kibana setup

1. Open http://localhost:5601 in your browser.
2. In Stack Management > Index Patterns, create an index pattern like `fit-data*`.
3. Use Visualize / Discover to inspect fields like `heart_rate`, `power`, `avg_power`, `training_stress_score`, etc.

## Troubleshooting

- Docker not starting: Restart Docker Desktop and ensure you have sufficient memory (~4GB) allocated.
- Elasticsearch port in use: Stop any other local Elasticsearch instances or change the ports in `docker-compose.yml`.
- Python errors: Activate `elk_env` before running scripts, and ensure dependencies are installed.
- Missing Apple Health export: `parse_apple_hr.py` will fail; either provide `apple_health_export/export.xml` or skip that step—`load_fit_to_es.py` will still run but won't add Apple HR enrichment.
- Indexing errors: Check Elasticsearch logs with `docker compose logs elasticsearch` from `~/elk-stack`.

## Files of interest

- `elk_fit_setup.sh` — helper script that automates the full setup.
- `parse_apple_hr.py` — parses Apple Health export XML into `daily_hr_summary.csv`.
- `load_fit_to_es.py` — parses Garmin `.fit` files and indexes records into Elasticsearch.
- `garmin/` — directory containing `.fit` files.

## License

This repo is for personal use. No license file is included.


