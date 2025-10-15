# Windows Setup Guide - Garmin .fit → ELK Loader

This guide will help you set up and run the Garmin fitness data analyzer on Windows.

## Prerequisites

1. **Docker Desktop for Windows**
   - Download from: https://www.docker.com/products/docker-desktop
   - Install and start Docker Desktop
   - Ensure WSL 2 is enabled (Docker Desktop will prompt if needed)

2. **Python 3.8+**
   - Download from: https://www.python.org/downloads/
   - During installation, check "Add Python to PATH"
   - Note: The setup uses `tqdm` for progress bars to show real-time indexing status

3. **PowerShell**
   - Already included with Windows 10/11

## Repository Structure

```
fit/
├── README.md                    # Main documentation
├── WINDOWS_SETUP.md             # Windows-specific setup guide
├── requirements.txt             # Python dependencies
├── .gitignore                   # Git ignore rules
├── elk_fit_setup.sh             # macOS/Linux setup script
├── setup_windows.ps1            # Windows setup script
├── scripts/                     # Python scripts
│   ├── load_fit_to_es.py        # Main data loader (bulk API)
│   └── parse_apple_hr.py        # Apple Health parser (optional)
└── garmin/                      # Your .fit files go here
    └── *.fit                    # Garmin activity files
```

## Quick Start (Automated)

1. Open PowerShell in the project directory:
   ```powershell
   cd D:\Projects\Roman\fit
   ```

2. Run the setup script:
   ```powershell
   .\setup_windows.ps1
   ```

   This will:
   - Check Docker is running
   - Create and start ELK Stack containers (with progress indicators)
   - Set up Python virtual environment
   - Install required packages (fitparse, elasticsearch, pandas, tqdm)
   - Load your .fit files into Elasticsearch using optimized bulk operations (typically completes in seconds)

3. Open Kibana in your browser: http://localhost:5601

## Manual Setup (Step-by-Step)

If you prefer to run steps manually or need to debug:

### 1. Start Docker Desktop
Ensure Docker Desktop is running (you should see the Docker icon in your system tray).

### 2. Set up ELK Stack

```powershell
# Create directory for ELK
mkdir $env:USERPROFILE\elk-stack
cd $env:USERPROFILE\elk-stack

# Create docker-compose.yml
@"
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
"@ | Out-File -FilePath docker-compose.yml -Encoding UTF8

# Start containers
docker compose up -d
```

### 3. Wait for Elasticsearch

```powershell
# Check if Elasticsearch is ready
curl http://localhost:9200/
```

Wait until you get a JSON response (may take 1-2 minutes).

### 4. Set up Python Environment

```powershell
# Return to project directory
cd D:\Projects\Roman\fit

# Create virtual environment
python -m venv elk_env

# Activate virtual environment
.\elk_env\Scripts\Activate.ps1

# If you get an execution policy error, run:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
# Or install individually: pip install fitparse "elasticsearch<9" pandas tqdm
```

### 5. Load Data

```powershell
# Make sure virtual environment is activated
.\elk_env\Scripts\Activate.ps1

# Load .fit files to Elasticsearch (with progress bar)
python scripts\load_fit_to_es.py
```

You'll see a progress bar showing file processing in real-time. The bulk API makes this very fast - typically completing in seconds rather than minutes.

### 6. View in Kibana

1. Open http://localhost:5601 in your browser
2. Go to **Management** → **Stack Management** → **Index Patterns**
3. Click **Create index pattern**
4. Enter pattern: `fit-data*`
5. Click **Next step** and **Create index pattern**
6. Go to **Discover** to view your data

## Available Metrics

The analyzer provides these metrics for your workouts:

- **Basic metrics**: heart_rate, power, speed, cadence, distance, altitude
- **Zones**: heart_rate_zone, power_zone
- **Session metrics**:
  - `avg_power` - Average power for the session
  - `avg_hr` - Average heart rate
  - `normalized_power` - Normalized power (NP)
  - `intensity_factor` - IF (NP/FTP)
  - `training_stress_score` - TSS
  - `hr_drift_pct` - Heart rate drift percentage
  - `moving_time_sec` - Moving time
  - `pause_time_sec` - Pause time
  - `distance_m` - Total distance
  - `elevation_gain_m` - Elevation gain

## Customization

Edit `scripts\load_fit_to_es.py` to customize:
- **FTP**: Line 11 - Update with your current FTP
- **Heart Rate Zones**: Lines 14-20
- **Power Zones**: Lines 22-30

After changes, reload data:
```powershell
.\elk_env\Scripts\Activate.ps1
python scripts\load_fit_to_es.py
```

The optimized bulk loading ensures re-indexing is quick, even with many files.

## Troubleshooting

### Docker not starting
- Restart Docker Desktop
- Ensure WSL 2 is installed and updated
- Check Docker Desktop settings: Settings → Resources (allocate at least 4GB RAM)

### Port already in use
```powershell
# Check what's using port 9200 or 5601
netstat -ano | findstr :9200
netstat -ano | findstr :5601

# Stop existing containers
cd $env:USERPROFILE\elk-stack
docker compose down
```

### Python virtual environment activation error
```powershell
# Set execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Try activating again
.\elk_env\Scripts\Activate.ps1
```

### Elasticsearch connection error
```powershell
# Check container status
docker ps

# View logs
cd $env:USERPROFILE\elk-stack
docker compose logs elasticsearch

# Restart containers
docker compose restart
```

## Useful Commands

```powershell
# Stop ELK Stack
cd $env:USERPROFILE\elk-stack
docker compose down

# Start ELK Stack
cd $env:USERPROFILE\elk-stack
docker compose up -d

# View logs
docker compose logs -f

# Reload data (from project directory)
cd D:\Projects\Roman\fit
.\elk_env\Scripts\Activate.ps1
python scripts\load_fit_to_es.py

# Add more .fit files
# 1. Copy new .fit files to the garmin\ folder
# 2. Run: python scripts\load_fit_to_es.py
```

## Apple Health Integration (Optional)

If you have an Apple Health export:

1. Export your Apple Health data from iPhone
2. Extract and place the export folder at: `apple_health_export\`
3. Ensure `export.xml` exists at: `apple_health_export\export.xml`
4. Run: `python parse_apple_hr.py`

This creates `daily_hr_summary.csv` with heart rate trends.

## Next Steps

- Create visualizations in Kibana for:
  - Power distribution over time
  - Heart rate zones
  - Training Stress Score trends
  - Power vs Heart Rate analysis
  - Weekly/monthly training volumes

- Build dashboards to track:
  - Fitness progression
  - Recovery metrics
  - Training load
  - Performance analytics

