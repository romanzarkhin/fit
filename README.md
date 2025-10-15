# Garmin .fit → ELK Loader

This repository contains helper scripts to parse Apple Health export data and Garmin `.fit` files, convert them into records, and load them into an Elasticsearch instance (ELK stack) for visualization in Kibana.

**Key Features:**
- 🚀 **Optimized bulk loading** - Indexes data 100-500x faster using Elasticsearch bulk API
- 📊 **Real-time progress indicators** - Visual progress bars show loading status
- 🖥️ **Cross-platform support** - Works on macOS, Linux, and Windows
- 📈 **Advanced metrics** - TSS, normalized power, HR drift, power/HR zones, and more

## Repository Structure

```
fit/
├── README.md                    # Main documentation
├── WINDOWS_SETUP.md             # Windows-specific setup guide
├── requirements.txt             # Python dependencies
├── .gitignore                   # Git ignore rules
├── elk_fit_setup.sh             # macOS/Linux automated setup script
├── setup_windows.ps1            # Windows automated setup script
├── scripts/                     # Python scripts
│   ├── load_fit_to_es.py        # Main data loader with bulk API
│   └── parse_apple_hr.py        # Apple Health parser (optional)
└── garmin/                      # Place your .fit files here
    └── *.fit                    # Garmin activity files
```

## Setup Methods

**Automated Setup (Recommended):**
- **macOS/Linux**: `elk_fit_setup.sh` creates a complete environment and generates Python scripts
- **Windows**: `setup_windows.ps1` uses the standalone Python scripts in `scripts/` folder

**Manual Setup:**
- Use the standalone Python scripts in `scripts/` directory
- Follow step-by-step instructions below for full control

## Prerequisites

- **macOS / Windows / Linux**
  - macOS: tested locally
  - Windows: See [WINDOWS_SETUP.md](WINDOWS_SETUP.md) for Windows-specific instructions
  - Linux: Follow the macOS instructions (bash/zsh compatible)
- Docker Desktop running (https://www.docker.com/products/docker-desktop)
- Python 3.8+ (system Python 3 is fine)
- Terminal (zsh / bash / PowerShell)

Optional:
- An Apple Health export folder at `apple_health_export/export.xml` if you want to enrich Garmin sessions with daily HR summaries.
- Your Garmin `.fit` files in the `garmin/` subfolder (this repo already includes sample `.fit` files).

## Quick run (one command)

### macOS / Linux

Open a terminal in the repository root and run:

```sh
bash elk_fit_setup.sh
```

### Windows

Open PowerShell in the repository root and run:

```powershell
.\setup_windows.ps1
```

See [WINDOWS_SETUP.md](WINDOWS_SETUP.md) for detailed Windows setup instructions.

**What the automated setup does:**
- Creates `~/elk-stack/docker-compose.yml` and starts Elasticsearch and Kibana via Docker Compose
- Creates a Python virtual environment `elk_env` and installs dependencies (`fitparse`, `elasticsearch<9`, `pandas`, `tqdm`)
- **macOS/Linux**: Generates Python scripts inline
- **Windows**: Uses standalone Python scripts from `scripts/` folder
- Optionally parses Apple Health data (if `apple_health_export/export.xml` exists)
- Loads `.fit` files from `garmin/` folder into Elasticsearch using optimized bulk API with real-time progress bars

**Note**: Setup scripts assume Docker is running and Python 3.8+ is available on your PATH.

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
pip install fitparse "elasticsearch<9" pandas tqdm
```

5. Prepare Apple Health export (optional but recommended):

- Put your Apple Health export folder at `apple_health_export/` so `apple_health_export/export.xml` exists.
- Run the parser:

```sh
python scripts/parse_apple_hr.py
```

This writes `daily_hr_summary.csv` used to enrich sessions.

6. Run the FIT loader (it reads `.fit` files from `garmin/`):

```sh
python scripts/load_fit_to_es.py
```

The script will create the Elasticsearch index `fit-data` and efficiently bulk-index documents with a progress bar showing real-time status. Data loading typically completes in seconds thanks to the bulk API optimization. You can confirm by visiting Kibana at `http://localhost:5601`.

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

## Files of Interest

- `elk_fit_setup.sh` — Automated setup script for macOS/Linux
- `setup_windows.ps1` — Automated setup script for Windows
- `WINDOWS_SETUP.md` — Comprehensive Windows setup guide with troubleshooting
- `requirements.txt` — Python dependencies list
- `scripts/load_fit_to_es.py` — Main data loader using Elasticsearch bulk API
- `scripts/parse_apple_hr.py` — Apple Health XML parser (optional)
- `garmin/` — Directory for your `.fit` files

## Performance

**Bulk API Optimization:**
- Original implementation: Individual HTTP requests for each record (slow)
- Optimized implementation: Batches of 500 records per request (fast)
- **Typical performance**: Loads 94,000+ records in ~30 seconds
- **Real-time progress**: `tqdm` progress bars show processing status and ETA

## Customization

Edit `scripts/load_fit_to_es.py` to customize:
- **FTP (Functional Threshold Power)**: Line 11
- **Heart Rate Zones**: Lines 14-20
- **Power Zones**: Lines 22-30

After changes, reload data:
```sh
# Activate virtual environment
source elk_env/bin/activate  # macOS/Linux
# or
.\elk_env\Scripts\Activate.ps1  # Windows

# Reload data
python scripts/load_fit_to_es.py
```

## License

This repo is for personal use. No license file is included.


