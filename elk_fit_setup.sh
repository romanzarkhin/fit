#!/bin/bash
# Step-by-step ELK Stack + Garmin .fit Analysis Setup on Mac

set -e  # Exit on error

echo "🚀 Starting ELK Stack + Garmin .fit Setup..."

# Save the original repo root before any directory changes
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. Create and start ELK Stack using Docker
echo "📦 Setting up Elasticsearch and Kibana..."
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
echo "✅ Elasticsearch and Kibana started"

# Wait for Elasticsearch to be ready
echo "⏳ Waiting for Elasticsearch to be ready..."
for i in {1..30}; do
  if curl -s http://localhost:9200 > /dev/null 2>&1; then
    echo "✅ Elasticsearch is ready"
    break
  fi
  echo "  Attempt $i/30..."
  sleep 2
done

# 2. Set up Python environment
echo "🐍 Setting up Python environment..."
cd "$REPO_ROOT"  # Go back to repo root

python3 -m venv elk_env
source elk_env/bin/activate

pip install --upgrade pip > /dev/null 2>&1
pip install fitparse "elasticsearch<9" pandas tqdm > /dev/null 2>&1
echo "✅ Python environment ready"

# 3. Run the bulk loader (recommended for production)
echo "📥 Loading Garmin .fit files into Elasticsearch..."
cd "$REPO_ROOT"
python3 scripts/es_bulk_loader.py --data-dir garmin --index fit-data##-enriched --enrichment-mode watch --health-export watch/apple_health_export/export.xml

# 4. Import pre-configured dashboard
echo "📊 Importing pre-configured dashboard..."
DASHBOARD_FILE="$REPO_ROOT/kibana/cyclist_dashboard.ndjson"
if [ -f "$DASHBOARD_FILE" ]; then
  # Wait a moment for index to be fully ready
  sleep 2
  curl -s -X POST "http://localhost:5601/api/saved_objects/_import?overwrite=true" \
    -H "kbn-xsrf: true" \
    --form "file=@$DASHBOARD_FILE" > /dev/null 2>&1
  if [ $? -eq 0 ]; then
    echo "✅ Dashboard imported successfully"
  else
    echo "⚠️  Dashboard import failed (Kibana may still be starting up)"
  fi
else
  echo "⚠️  Dashboard file not found at $DASHBOARD_FILE"
fi

# 5. Print access information
echo ""
echo "✅ Setup complete!"
echo ""
echo "📊 Access Kibana Dashboard:"
echo "   URL: http://localhost:5601"
echo ""
echo "📖 Next steps:"
echo "   1. Open http://localhost:5601 in your browser"
echo "   2. Go to Dashboards and select 'cyclist' to view pre-configured visualizations"
echo "   3. Use Discover for ad-hoc exploration of your cycling metrics"
echo ""
echo "📝 Available metrics:"
echo "   - heart_rate, power, cadence, speed"
echo "   - training_stress_score (TSS)"
echo "   - normalized_power, intensity_factor"
echo "   - hr_drift_pct (heart rate drift)"
echo "   - avg_power, avg_hr, distance_m, elevation_gain_m"
echo ""
echo "For more info, see README.md"
