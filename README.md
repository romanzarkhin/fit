# Garmin .fit → ELK Loader

This repository contains helper scripts to parse Garmin `.fit` files, compute advanced cycling metrics (TSS, normalized power, intensity factor, HR drift), and load them into an Elasticsearch instance (ELK stack) for visualization in Kibana.

Two loading approaches are available:
- **`load_fit_to_es.py`** — simple, single-threaded loader (suitable for small datasets)
- **`scripts/es_bulk_loader.py`** (v2.1) — robust bulk loader with retry logic, configurable chunk sizes, progress tracking, and detailed failure logging (recommended for production)

## Prerequisites

**Supported Platforms:**
- **macOS** (tested locally) — use `bash elk_fit_setup.sh`
- **Linux** (WSL or native) — use `bash elk_fit_setup.sh`  
- **Windows** (v2.3+) — PowerShell script planned; see Manual Setup below

**Requirements:**
- Docker Desktop running (https://www.docker.com/products/docker-desktop)
- Python 3.8+
  - **macOS/Linux:** `python3` on your PATH
  - **Windows:** https://www.python.org or Microsoft Store
- Terminal:
  - **macOS/Linux:** bash or zsh  
  - **Windows:** PowerShell (built-in) or bash via WSL/Git Bash

**Optional:**
- An Apple Health export at `watch/apple_health_export/export.xml` for v2.2 enrichment  
- Your Garmin `.fit` files in the `garmin/` subfolder (sample files included for testing)

## Quick run (one command)

**macOS / Linux:**

```bash
bash elk_fit_setup.sh
```

**Windows (v2.3+):**

Windows PowerShell support planned for v2.3. Use **Manual Setup** below or [WSL](https://learn.microsoft.com/en-us/windows/wsl/install) for now.

---

**What the setup script does:**
- Creates `~/elk-stack/docker-compose.yml` and starts Elasticsearch + Kibana  
- Creates Python virtual environment with all dependencies
- Loads all `.fit` files from `garmin/` with **v2.2 enrichment enabled** (Apple Watch optional)
- **Automatically imports the pre-configured "Cyclist" dashboard** (10 Lens visualizations)

## Step-by-step manual run (recommended for debugging)

### 1. Start Docker Desktop

Ensure Docker Desktop is running.

### 2. Create and start the ELK stack

**macOS / Linux:**

```bash
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

**Windows (PowerShell):**

```powershell
New-Item -ItemType Directory -Path "$env:USERPROFILE\elk-stack" -Force | Set-Location
$compose = @"
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
"@
$compose | Out-File -FilePath docker-compose.yml -Encoding UTF8
docker compose up -d
```

### 3. Wait for Elasticsearch to be ready

(Takes ~1-2 minutes)

**macOS / Linux:**

```bash
curl -sS http://localhost:9200/ | jq
```

**Windows (PowerShell):**

```powershell
Invoke-RestMethod -Uri "http://localhost:9200/" -Method Get
```

### 4. Create and activate Python virtual environment

**macOS / Linux:**

```bash
cd /path/to/fit
python3 -m venv elk_env
source elk_env/bin/activate
pip install --upgrade pip
pip install fitparse "elasticsearch<9" pandas tqdm
```

**Windows (Command Prompt):**

```batch
cd C:\path\to\fit
python -m venv elk_env
elk_env\Scripts\activate.bat
pip install --upgrade pip
pip install fitparse "elasticsearch<9" pandas tqdm
```

**Windows (PowerShell):**

```powershell
Set-Location C:\path\to\fit
python -m venv elk_env
.\elk_env\Scripts\Activate.ps1
pip install --upgrade pip
pip install fitparse "elasticsearch<9" pandas tqdm
```

### 5. Run the bulk loader with v2.2 enrichment

**All platforms (venv activated):**

```bash
# Basic: Load without enrichment
python3 scripts/es_bulk_loader.py --data-dir garmin --index fit-data

# With v2.2 enrichment (Apple Watch optional):
python3 scripts/es_bulk_loader.py \
  --data-dir garmin \
  --index fit-data \
  --enrichment-mode watch \
  --health-export watch/apple_health_export/export.xml
```

The script creates the index and loads all records. Verify at `http://localhost:5601`.

**Configuring the folder location:**

The script supports multiple ways to specify the folder containing `.fit` files (in order of precedence):

1. CLI argument: `python load_fit_to_es.py --folder /path/to/fit/files`
2. Environment variable: `FIT_FOLDER=/path/to/fit/files python load_fit_to_es.py`
3. Default: `./garmin` (relative to the script location)

## Kibana setup

1. Open http://localhost:5601 in your browser.
2. In Stack Management > Index Patterns, create an index pattern like `fit-data*`.
3. Use Visualize / Discover to inspect fields like `heart_rate`, `power`, `avg_power`, `training_stress_score`, etc.

## Advanced: Bulk Loader Features (v2.1+)

The `scripts/es_bulk_loader.py` is the recommended production loader with:
- **Robust bulk indexing** using `elasticsearch.helpers.bulk`
- **Configurable chunk sizes** (default: 500 documents per request)
- **Retry logic with exponential backoff**
- **Progress tracking** with tqdm
- **Detailed failure logging** to `es_bulk_failures.log`
- **Index optimization** (disables refresh during load, restores after)
- **v2.2: Apple Watch Enrichment** (optional) — Daily Apple Health metrics per session

### Basic usage:

```bash
python3 scripts/es_bulk_loader.py --data-dir garmin --index fit-data
```

### v2.2 Enrichment with Apple Watch:

```bash
python3 scripts/es_bulk_loader.py \
  --data-dir garmin \
  --index fit-data \
  --enrichment-mode watch \
  --health-export watch/apple_health_export/export.xml

# With custom recovery thresholds:
python3 scripts/es_bulk_loader.py \
  --data-dir garmin \
  --index fit-data \
  --enrichment-mode watch \
  --health-export watch/apple_health_export/export.xml \
  --baseline-resting-hr 50 \
  --hrv-recovery-threshold 30
```

### Advanced options:

```bash
# Custom chunk size and ES host
ES_HOST=http://localhost:9200 python3 scripts/es_bulk_loader.py \
  --data-dir garmin --index fit-data --chunk-size 1000

# Skip index creation
python3 scripts/es_bulk_loader.py \
  --data-dir garmin --index fit-data --skip-create

# Debug: Dump parsed health data to CSV
python3 scripts/es_bulk_loader.py \
  --data-dir garmin --index fit-data \
  --enrichment-mode watch \
  --health-export watch/apple_health_export/export.xml \
  --dump-health-csv /tmp/debug.csv
```

### Output & Logging:

- Console log and file log (`es_bulk_loader.log`) with full details
- Per-item failure logging in `es_bulk_failures.log`
- Summary printed at the end (success/failure counts)

## Troubleshooting

**General:**
- Docker not starting: Restart Docker Desktop (need ~4GB memory)
- Elasticsearch port in use: Stop other ES instances or change ports in `docker-compose.yml`
- Python errors: Activate `elk_env` before running scripts
- Indexing errors: Check `docker compose logs elasticsearch` from `~/elk-stack`

**macOS/Linux:**
- `bash: python3: command not found` — Install Python 3.8+ or check PATH
- `source: command not found` — Use bash/zsh, not sh

**Windows:**
- `python: command not found` — Add to PATH or use full path
- `Activate.ps1 cannot be loaded` — Run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
- Native Windows setup: v2.3 planned; use manual steps or WSL for now

**v2.2 Enrichment:**
- `Enrichment mode 'watch' requires parse_apple_hr` — Check venv activated; verify `watch/apple_health_export/export.xml` exists
- No health data matched — Verify export has records for your FIT file dates

## Files of interest

- `elk_fit_setup.sh` — helper script that automates the full setup and imports the dashboard.
- `load_fit_to_es.py` — deprecated wrapper; use `scripts/es_bulk_loader.py` instead.
- `scripts/es_bulk_loader.py` — production-ready bulk loader with retry logic, progress tracking, and detailed logging.
- `scripts/export_kibana_dashboard.py` — utility to export dashboards from Kibana to NDJSON format.
- `garmin/` — directory containing Garmin `.fit` files.
- `kibana/cyclist_dashboard.ndjson` — pre-configured Kibana dashboard with 10 Lens visualizations (NDJSON format). Automatically imported during setup.

## Feedback & Collaboration

This project is actively evolving. I'd love your input!

**Have ideas for improvements, bug reports, or want to collaborate?**

📧 **Reach out on LinkedIn:** https://www.linkedin.com/in/roman-zarkhin/

Send me a DM with:
- Feature requests or improvements you'd like to see
- Performance insights from your own cycling data
- Integration ideas (Strava API?)
- Bug reports or edge cases you've encountered
- General feedback on the dashboard or metrics

Your input helps shape the future of this project. Looking forward to connecting!

## License

This repo is for personal use. No license file is included.

## Developer Guide (concise)

- **Primary entry (production):** `python3 scripts/es_bulk_loader.py --data-dir garmin --index fit-data`
- **Debug / small runs:** `python3 scripts/load_fit_to_es.py --folder garmin`
- **Backward compatibility:** `python load_fit_to_es.py` (root wrapper delegates to `scripts/`)

If you're contributing or iterating on the project, follow this quick developer checklist:

- Clone the repo and run the setup script: `bash elk_fit_setup.sh`
- Ensure Docker Desktop is running and `python3` is available
- Use the bulk loader for realistic loads (it includes retry/backoff and logging)
- Keep parsing/enrichment logic inside `scripts/` to avoid duplication

Architecture summary (short): code is organized so the bulk loader is the canonical pipeline; lightweight loader exists for debugging and a thin root wrapper preserves backwards compatibility.

## Apple Watch Enrichment (v2.2) — NEW! 🎉

**v2.2 adds optional Apple Watch enrichment.** Combine Garmin cycling metrics with daily Apple Health data for deeper insights.

### Quick Start

1. Export your Apple Health: Open Apple Health app → Profile → Export Health Data
2. Unzip to `watch/apple_health_export/` in this repo
3. Run bulk loader with `--enrichment-mode watch` flag

### What Gets Added

**Daily Apple Watch metrics** (`watch.*`):
- `resting_hr`, `daily_avg_hr`, `daily_min_hr`, `daily_max_hr` 
- `hrv` (heart rate variability)
- `step_count`, `active_energy_kcal`

**Computed session metrics** (`computed.*`):
- `fatigue_index` = (session_avg_hr / resting_hr) - 1
- `recovery_ready` = (hrv > threshold) AND (resting_hr < baseline)  
- `session_intensity_index` = (normalized_power / FTP) × (avg_hr / daily_max_hr)

### Design Principles

- **Runtime XML parsing** — No stale CSV required
- **In-memory enrichment** — Sessions matched to daily summaries by date
- **Graceful degradation** — Missing metrics don't break indexing
- **Optional debug output** — `--dump-health-csv /tmp/debug.csv`
- **Configurable thresholds** — `--baseline-resting-hr 50 --hrv-recovery-threshold 30`

### Example: Custom Thresholds

```bash
python3 scripts/es_bulk_loader.py \
  --data-dir garmin \
  --index fit-data \
  --enrichment-mode watch \
  --health-export watch/apple_health_export/export.xml \
  --baseline-resting-hr 48 \
  --hrv-recovery-threshold 35
```

### Dashboard Integration

The pre-configured Kibana dashboard includes visualizations for enriched metrics.

### Developer Notes

Full implementation details in `/plan/parser-out-watch-int.md` (local, untracked).

### Platform Support

- **macOS/Linux:** Fully supported  
- **Windows:** v2.3 planned (Python code already cross-platform)

## Kibana Dashboard (v2.1+)

A pre-configured dashboard is automatically imported during setup and available at `kibana/cyclist_dashboard.ndjson`.

### Dashboard Contents

The "Cyclist" dashboard includes 10 Lens visualizations:
1. **Time in HR Zones** — Donut chart showing distribution across heart rate zones (assess polarized/pyramidal/sweet spot training)
2. **Power & Heart Rate Over Time** — Dual-axis line chart correlating power output to heart rate over weekly buckets
3. **Session Summary Table** — Daily aggregated metrics (median HR, power, NP, TSS, IF, distance, elevation)
4. **Time in Power Zones** — Stacked bar chart showing weekly distribution across power zones (Z1–Z7)
5. **Aerobic Decoupling Trend** — Line chart of heart rate drift percentage by week (monitor fatigue resistance)
6. **Training Load Over Time (TSS)** — Area chart with reference lines for low (49), race (150) thresholds
7. **Power vs Heart Rate** — Scatter plot filtered for high-intensity sessions (5min power ≥210, IF ≥0.85)
8. **VO2Max Over Time** — Line chart with reference lines for estimated VO2Max categories (Low 30, Comp 38, Adv 44, Elite 47)
9. **Max 5min Power Over Time** — Area chart of peak 5-minute power trend
10. **Power vs Heart Rate (Zones)** — Line chart comparing avg HR across top 3 power zones

### Manual Dashboard Import

If you need to reimport the dashboard after clearing Kibana:

```bash
curl -X POST "http://localhost:5601/api/saved_objects/_import?overwrite=true" \
  -H "kbn-xsrf: true" \
  --form file=@kibana/cyclist_dashboard.ndjson
```

### Customizing Your Dashboard

To export your customized dashboard back to the repository via Kibana UI:

1. Open your dashboard in Kibana
2. Go to **Stack Management** → **Saved Objects** → **Dashboards** → Find "Cyclist"
3. Click the **⋮ (three dots)** menu and select **Export**
4. Replace `kibana/cyclist_dashboard.ndjson` with your exported file


