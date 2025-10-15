# Windows Setup Script for Garmin .fit to ELK Loader
# Run this script in PowerShell

Write-Host "Setting up Garmin .fit to ELK Stack on Windows" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Docker
Write-Host "Step 1: Checking Docker Desktop..." -ForegroundColor Yellow
$dockerRunning = docker ps 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop is not running or not installed." -ForegroundColor Red
    Write-Host "   Please install Docker Desktop from: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    Write-Host "   After installation, start Docker Desktop and run this script again." -ForegroundColor Yellow
    exit 1
}
Write-Host "SUCCESS: Docker is running" -ForegroundColor Green

# Step 2: Set up ELK Stack
Write-Host ""
Write-Host "Step 2: Setting up ELK Stack..." -ForegroundColor Yellow

$elkPath = "$env:USERPROFILE\elk-stack"
if (-not (Test-Path $elkPath)) {
    New-Item -ItemType Directory -Path $elkPath -Force | Out-Null
}

$dockerCompose = @'
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
'@

Set-Content -Path "$elkPath\docker-compose.yml" -Value $dockerCompose
Write-Host "SUCCESS: Created docker-compose.yml at $elkPath" -ForegroundColor Green

# Check if images exist
Write-Host "  Checking Docker images..." -ForegroundColor Yellow
$esImageExists = docker images -q docker.elastic.co/elasticsearch/elasticsearch:8.13.4
$kibanaImageExists = docker images -q docker.elastic.co/kibana/kibana:8.13.4

if (-not $esImageExists -or -not $kibanaImageExists) {
    Write-Host "  Downloading Docker images (this may take a few minutes on first run)..." -ForegroundColor Yellow
} else {
    Write-Host "  Images already cached, starting containers..." -ForegroundColor Yellow
}

# Start Docker Compose
Push-Location $elkPath
docker compose up -d
Pop-Location
Write-Host "SUCCESS: ELK Stack containers started" -ForegroundColor Green

# Step 3: Wait for Elasticsearch
Write-Host ""
Write-Host "Step 3: Waiting for Elasticsearch to be ready..." -ForegroundColor Yellow
$maxRetries = 30
$retryCount = 0
$esReady = $false
$startTime = Get-Date

while ((-not $esReady) -and ($retryCount -lt $maxRetries)) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:9200/" -UseBasicParsing -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $esReady = $true
            $elapsed = [math]::Round(((Get-Date) - $startTime).TotalSeconds)
            Write-Host "SUCCESS: Elasticsearch is ready (took $elapsed seconds)" -ForegroundColor Green
        }
    } catch {
        $retryCount++
        $elapsed = [math]::Round(((Get-Date) - $startTime).TotalSeconds)
        Write-Host "  Waiting for Elasticsearch... ($elapsed seconds)" -ForegroundColor Gray
        Start-Sleep -Seconds 2
    }
}

if (-not $esReady) {
    Write-Host "ERROR: Elasticsearch failed to start. Check logs with: docker compose logs elasticsearch" -ForegroundColor Red
    exit 1
}

# Step 4: Set up Python environment
Write-Host ""
Write-Host "Step 4: Setting up Python virtual environment..." -ForegroundColor Yellow

# Check if Python is available
$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $version = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $pythonCmd = $cmd
            Write-Host "SUCCESS: Found Python: $version" -ForegroundColor Green
            break
        }
    } catch {
        continue
    }
}

if (-not $pythonCmd) {
    Write-Host "ERROR: Python not found. Please install Python 3.8+ from https://www.python.org/" -ForegroundColor Red
    exit 1
}

# Create virtual environment
if (-not (Test-Path "elk_env")) {
    Write-Host "  Creating virtual environment..." -ForegroundColor Yellow
    & $pythonCmd -m venv elk_env
    Write-Host "SUCCESS: Virtual environment created" -ForegroundColor Green
}

# Activate and install dependencies
Write-Host "  Installing dependencies..." -ForegroundColor Yellow
.\elk_env\Scripts\python.exe -m pip install --upgrade pip --quiet
.\elk_env\Scripts\python.exe -m pip install fitparse "elasticsearch<9" pandas tqdm --quiet
Write-Host "SUCCESS: Dependencies installed (fitparse, elasticsearch, pandas, tqdm)" -ForegroundColor Green

# Step 5: Parse Apple Health (optional)
Write-Host ""
Write-Host "Step 5: Parsing Apple Health data (optional)..." -ForegroundColor Yellow
if (Test-Path "apple_health_export\export.xml") {
    Write-Host "  Found Apple Health export, parsing..." -ForegroundColor Yellow
    .\elk_env\Scripts\python.exe scripts\parse_apple_hr.py
} else {
    Write-Host "  INFO: Apple Health export not found at apple_health_export\export.xml" -ForegroundColor Gray
    Write-Host "  Skipping Apple Health parsing (optional step)" -ForegroundColor Gray
}

# Step 6: Load .fit files to Elasticsearch
Write-Host ""
Write-Host "Step 6: Loading .fit files to Elasticsearch..." -ForegroundColor Yellow

# Count .fit files
$fitFileCount = (Get-ChildItem -Path "garmin" -Filter "*.fit" -ErrorAction SilentlyContinue).Count
if ($fitFileCount -gt 0) {
    Write-Host "  Found $fitFileCount .fit files in garmin folder" -ForegroundColor Gray
}

.\elk_env\Scripts\python.exe scripts\load_fit_to_es.py

# Step 7: Instructions
Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Open Kibana in your browser: http://localhost:5601" -ForegroundColor White
Write-Host "2. Go to Stack Management > Index Patterns" -ForegroundColor White
Write-Host "3. Create an index pattern: fit-data*" -ForegroundColor White
Write-Host "4. Use Discover/Visualize to explore your Garmin data" -ForegroundColor White
Write-Host ""
Write-Host "Commands:" -ForegroundColor Cyan
Write-Host "  View ELK logs:    cd $elkPath; docker compose logs -f" -ForegroundColor White
Write-Host "  Stop ELK Stack:   cd $elkPath; docker compose down" -ForegroundColor White
Write-Host "  Restart ELK:      cd $elkPath; docker compose restart" -ForegroundColor White
Write-Host "  Reload data:      .\elk_env\Scripts\python.exe scripts\load_fit_to_es.py" -ForegroundColor White
Write-Host ""
